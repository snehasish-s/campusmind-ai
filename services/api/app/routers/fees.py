"""Invoice ledger and optional Razorpay checkout. Browser callbacks never settle fees alone."""

import csv
import hashlib
import hmac
import io
import json
import secrets
from datetime import datetime, timezone
from typing import Literal
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models as m
from ..config import settings
from ..security import current_user, require, ADMINS, scoped, audit, csv_safe, rate_limit
from ..campus_services import notify
from .campus import Audience, recipients

router = APIRouter(prefix="/campus/fees", tags=["Fee invoices, payments and receipts"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PlanInput(Strict):
    reference: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=3, max_length=200)
    category: Literal["tuition", "exam", "hostel", "transport", "other"] = "tuition"
    term: str = Field(min_length=2, max_length=80)
    amount_paise: int = Field(strict=True, ge=100, le=100000000)
    due_at: datetime
    audience: Audience = Field(default_factory=Audience)


def payment_config(tenant):
    config = settings()
    if config.payment_provider == "razorpay" and (
        not config.razorpay_key_id or not config.razorpay_key_secret or config.payment_institution_id != tenant
    ):
        raise HTTPException(503, "The institution's merchant account is not configured. Ask your administrator.")
    return config


def payment_environment(config):
    return "demo" if config.payment_provider == "demo" else "test" if config.razorpay_key_id.startswith("rzp_test_") else "live"


def gateway(method, path, **kwargs):
    config = settings()
    try:
        response = httpx.request(
            method, "https://api.razorpay.com/v1/" + path, auth=(config.razorpay_key_id, config.razorpay_key_secret), timeout=20, **kwargs
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Invalid provider payload")
        return result
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            503, "Payment provider unavailable. No fee has been marked paid. Retry status verification before paying again."
        )


def invoice_access(db, user, invoice_id):
    invoice = scoped(db, m.FeeInvoice, user, invoice_id)
    if user.role == "student":
        if invoice.user_id != user.id:
            raise HTTPException(404, "Invoice not found.")
    else:
        require(user, ADMINS)
    return invoice


def invoice_view(db, invoice, plan=None, student=None, payments=None):
    plan = plan or db.get(m.FeePlan, invoice.plan_id)
    student = student or db.get(m.User, invoice.user_id)
    payments = (
        payments
        if payments is not None
        else list(
            db.scalars(select(m.PaymentOrder).where(m.PaymentOrder.invoice_id == invoice.id).order_by(m.PaymentOrder.created_at.desc()))
        )
    )
    return {
        "id": invoice.id,
        "reference": plan.reference,
        "title": plan.title,
        "category": plan.category,
        "term": plan.term,
        "student": student.full_name,
        "roll_no": student.roll_no,
        "user_id": student.id,
        "amount_paise": invoice.amount_paise,
        "due_at": plan.due_at,
        "status": invoice.status,
        "paid_at": invoice.paid_at,
        "overdue": invoice.status == "unpaid" and plan.due_at < m.now(),
        "payments": [
            {
                "id": p.id,
                "provider": p.provider,
                "environment": p.environment,
                "status": p.status,
                "receipt_number": p.receipt_number,
                "settled_at": p.settled_at,
            }
            for p in payments
        ],
    }


@router.get("")
def invoices(q: str = "", user=Depends(current_user), db: Session = Depends(get_db)):
    query = (
        select(m.FeeInvoice, m.FeePlan, m.User)
        .join(m.FeePlan, m.FeePlan.id == m.FeeInvoice.plan_id)
        .join(m.User, m.User.id == m.FeeInvoice.user_id)
        .where(m.FeeInvoice.institution_id == user.institution_id)
    )
    if user.role == "student":
        query = query.where(m.FeeInvoice.user_id == user.id)
    else:
        require(user, ADMINS)
    payments = {}
    payment_query = select(m.PaymentOrder).where(m.PaymentOrder.institution_id == user.institution_id)
    if user.role == "student":
        payment_query = payment_query.join(m.FeeInvoice, m.FeeInvoice.id == m.PaymentOrder.invoice_id).where(
            m.FeeInvoice.user_id == user.id
        )
    for order in db.scalars(payment_query.order_by(m.PaymentOrder.created_at.desc())):
        payments.setdefault(order.invoice_id, []).append(order)
    rows = [
        invoice_view(db, invoice, plan, student, payments.get(invoice.id, []))
        for invoice, plan, student in db.execute(query.order_by(m.FeeInvoice.created_at.desc()))
    ]
    if q:
        rows = [r for r in rows if q.casefold() in (r["title"] + r["student"] + r["roll_no"] + r["reference"]).casefold()]
    config = settings()
    return {
        "invoices": rows,
        "provider": config.payment_provider,
        "test_mode": config.payment_provider == "demo" or config.razorpay_key_id.startswith("rzp_test_"),
        "configured": config.payment_provider == "demo"
        or bool(config.payment_institution_id == user.institution_id and config.razorpay_key_id and config.razorpay_key_secret),
        "totals": {
            "billed_paise": sum(r["amount_paise"] for r in rows if r["status"] != "void"),
            "collected_paise": sum(r["amount_paise"] for r in rows if r["status"] == "paid"),
            "outstanding_paise": sum(r["amount_paise"] for r in rows if r["status"] in {"unpaid", "demo_paid"}),
            "demo_paid_paise": sum(r["amount_paise"] for r in rows if r["status"] == "demo_paid"),
        },
    }


@router.post("/plans/preview")
def preview(body: PlanInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    if body.audience.department_id:
        scoped(db, m.Department, user, body.audience.department_id)
    targets = recipients(db, user, body.audience.model_dump())
    return {
        "students": len(targets),
        "total_paise": len(targets) * body.amount_paise,
        "notice": "Confirmation issues fixed invoices to these students. Future cohort changes will not reassign their invoices.",
    }


@router.post("/plans")
def issue(body: PlanInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    rate_limit("fee-issue:" + user.id, 20, 3600)
    # Tenant lock + reference uniqueness protects duplicate bulk issue requests.
    db.scalar(select(m.Institution).where(m.Institution.id == user.institution_id).with_for_update())
    existing = db.scalar(select(m.FeePlan).where(m.FeePlan.institution_id == user.institution_id, m.FeePlan.reference == body.reference))
    if existing:
        return {
            "id": existing.id,
            "already_issued": True,
            "invoices": len(list(db.scalars(select(m.FeeInvoice.id).where(m.FeeInvoice.plan_id == existing.id)))),
        }
    if body.audience.department_id:
        scoped(db, m.Department, user, body.audience.department_id)
    audience = body.audience.model_dump()
    targets = recipients(db, user, audience)
    if not targets:
        raise HTTPException(422, "No students match this audience. Check cohort assignments before issuing fees.")
    due = body.due_at.astimezone(timezone.utc).replace(tzinfo=None) if body.due_at.tzinfo else body.due_at
    plan = m.FeePlan(
        institution_id=user.institution_id,
        reference=body.reference,
        title=body.title,
        category=body.category,
        term=body.term,
        amount_paise=body.amount_paise,
        due_at=due,
        audience=audience,
        created_by=user.id,
    )
    db.add(plan)
    db.flush()
    for target in targets:
        invoice = m.FeeInvoice(institution_id=user.institution_id, plan_id=plan.id, user_id=target.id, amount_paise=body.amount_paise)
        db.add(invoice)
        notify(
            db,
            user.institution_id,
            target.id,
            f"fee-issued:{plan.id}",
            "A fee invoice has been issued",
            f"{plan.title} · {plan.term} · INR {body.amount_paise / 100:.2f}. Open Campus Hub → Fees to review and pay.",
            "fee",
        )
    audit(db, user, "fees.issued", plan.id, {"reference": body.reference, "students": len(targets), "amount_paise": body.amount_paise})
    db.commit()
    return {"id": plan.id, "invoices": len(targets)}


@router.get("/export")
def export(user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    rows = invoices(user=user, db=db)["invoices"]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["invoice_id", "registration_no", "student", "fee", "term", "amount_INR", "status", "due_at"])
    for row in rows:
        writer.writerow(
            [
                csv_safe(v)
                for v in [
                    row["id"],
                    row["roll_no"],
                    row["student"],
                    row["title"],
                    row["term"],
                    f"{row['amount_paise'] / 100:.2f}",
                    row["status"],
                    row["due_at"].isoformat(),
                ]
            ]
        )
    audit(db, user, "fees.exported")
    db.commit()
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="campusmind-fees.csv"'})


class OrderInput(Strict):
    idempotency_key: str = Field(min_length=16, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


def order_view(order, config):
    return {
        "id": order.id,
        "provider": order.provider,
        "order_id": order.provider_order_id,
        "amount": order.amount_paise,
        "currency": "INR",
        "key_id": config.razorpay_key_id if order.provider == "razorpay" else None,
        "status": order.status,
        "test_mode": order.environment != "live",
    }


@router.post("/{invoice_id}/orders")
def create_order(invoice_id: str, body: OrderInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    rate_limit("payment-order:" + user.id, 10, 300)
    invoice = invoice_access(db, user, invoice_id)
    db.refresh(invoice, with_for_update=True)
    config = payment_config(user.institution_id)
    if invoice.status in {"paid", "void"}:
        raise HTTPException(409, "This invoice is already paid or void.")
    provider = config.payment_provider
    environment = payment_environment(config)
    order = db.scalar(
        select(m.PaymentOrder).where(
            m.PaymentOrder.invoice_id == invoice.id, m.PaymentOrder.provider == provider, m.PaymentOrder.environment == environment
        )
    )
    if order:
        if order.status == "uncertain":
            raise HTTPException(
                409, "A provider request needs reconciliation. Ask your finance administrator to verify it before retrying."
            )
        return order_view(order, config)
    order = m.PaymentOrder(
        institution_id=user.institution_id,
        invoice_id=invoice.id,
        idempotency_key=body.idempotency_key,
        provider=provider,
        environment=environment,
        amount_paise=invoice.amount_paise,
    )
    db.add(order)
    db.flush()
    if provider == "razorpay":
        try:
            result = gateway(
                "POST",
                "orders",
                json={"amount": invoice.amount_paise, "currency": "INR", "receipt": order.id, "notes": {"invoice_id": invoice.id}},
            )
            if not result.get("id") or result.get("amount") != invoice.amount_paise or result.get("currency") != "INR":
                raise HTTPException(503, "Provider returned an invalid order. Finance reconciliation is required.")
            order.provider_order_id = result["id"]
        except HTTPException:
            order.status = "uncertain"
            db.commit()
            raise
    audit(db, user, "payment.order_created", invoice.id, {"provider": provider})
    db.commit()
    return order_view(order, config)


def settle(db, order, payment_id, test=False):
    invoice = db.scalar(select(m.FeeInvoice).where(m.FeeInvoice.id == order.invoice_id).with_for_update())
    db.refresh(order, with_for_update=True)
    if order.status == "paid":
        if order.provider_payment_id != payment_id:
            raise HTTPException(409, "Another payment was already recorded for this order. Contact finance.")
        return
    if invoice.status == "void" or (invoice.status == "paid" and not test):
        raise HTTPException(409, "Invoice cannot accept another payment. Finance review required.")
    order.status, order.provider_payment_id, order.settled_at = "paid", payment_id, m.now()
    order.receipt_number = ("TEST-" if test else "CM-") + secrets.token_hex(12).upper()
    invoice.status, invoice.paid_at = "demo_paid" if test else "paid", m.now()
    notify(
        db,
        invoice.institution_id,
        invoice.user_id,
        f"paid:{order.id}",
        "Demo payment recorded" if test else "Fee payment received",
        f"Receipt {order.receipt_number} is available in Campus Hub → Fees." + (" No money was collected." if test else ""),
        "payment",
    )
    db.add(
        m.AuditLog(
            institution_id=invoice.institution_id,
            actor_id=invoice.user_id,
            action="payment.test_settled" if test else "payment.captured",
            target_id=invoice.id,
            details={"order_id": order.id, "amount_paise": order.amount_paise},
        )
    )


@router.post("/orders/{order_id}/demo-complete")
def demo_complete(order_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    if settings().payment_provider != "demo":
        raise HTTPException(403, "Local demonstration payments are disabled.")
    order = scoped(db, m.PaymentOrder, user, order_id)
    invoice_access(db, user, order.invoice_id)
    if order.provider != "demo":
        raise HTTPException(403, "This is not a demonstration order.")
    settle(db, order, "demo_" + order.id, test=True)
    db.commit()
    return {"receipt_id": order.id, "status": "demo_paid", "money_collected": False}


def verify_capture(db, order, payment_id):
    config = payment_config(order.institution_id)
    if order.environment != payment_environment(config):
        raise HTTPException(
            409, "This order belongs to a different payment environment. Ask finance to reconcile using the matching merchant keys."
        )
    result = gateway("GET", "payments/" + payment_id)
    if (
        result.get("order_id") != order.provider_order_id
        or result.get("amount") != order.amount_paise
        or result.get("currency") != "INR"
        or result.get("status") != "captured"
        or not result.get("captured")
    ):
        raise HTTPException(
            409, "A captured payment matching this order, amount and currency has not been confirmed. Retry verification later."
        )
    settle(db, order, payment_id, test=config.razorpay_key_id.startswith("rzp_test_"))


class VerifyInput(Strict):
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]+$", max_length=100)
    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]+$", max_length=100)
    razorpay_signature: str = Field(min_length=64, max_length=64)


@router.post("/orders/{order_id}/verify")
def verify(order_id: str, body: VerifyInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, {"student"})
    rate_limit("payment-verify:" + user.id, 20, 300)
    order = scoped(db, m.PaymentOrder, user, order_id)
    invoice_access(db, user, order.invoice_id)
    config = payment_config(user.institution_id)
    if config.payment_provider != "razorpay" or order.provider != "razorpay" or body.razorpay_order_id != order.provider_order_id:
        raise HTTPException(422, "Payment order does not match.")
    signature = hmac.new(
        config.razorpay_key_secret.encode(), f"{order.provider_order_id}|{body.razorpay_payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, body.razorpay_signature):
        raise HTTPException(400, "Payment signature is invalid.")
    verify_capture(db, order, body.razorpay_payment_id)
    db.commit()
    return {"receipt_id": order.id, "status": "verified"}


@router.post("/orders/{order_id}/refresh")
def refresh_payment(order_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    rate_limit("payment-refresh:" + user.id, 10, 300)
    order = scoped(db, m.PaymentOrder, user, order_id)
    invoice_access(db, user, order.invoice_id)
    config = payment_config(user.institution_id)
    if order.provider != "razorpay" or not order.provider_order_id or order.environment != payment_environment(config):
        raise HTTPException(409, "This order cannot be refreshed with the configured merchant environment.")
    if order.status != "paid":
        payments = gateway("GET", f"orders/{order.provider_order_id}/payments")
        captured = [p for p in payments.get("items", []) if p.get("status") == "captured"]
        if captured:
            payment_id = captured[0].get("id", "")
            if not isinstance(payment_id, str) or not payment_id.startswith("pay_") or not payment_id[4:].isalnum():
                raise HTTPException(503, "Invalid payment reference returned by provider.")
            verify_capture(db, order, payment_id)
            db.commit()
    return {"status": order.status, "receipt_id": order.id if order.receipt_number else None}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    config = settings()
    if config.payment_provider != "razorpay" or not config.razorpay_webhook_secret:
        raise HTTPException(503, "Payment webhooks are not configured.")
    raw = await request.body()
    signature = hmac.new(config.razorpay_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(400, "Invalid webhook signature.")
    try:
        event = json.loads(raw)
        if event.get("event") != "payment.captured":
            return {"ignored": True}
        payment = event["payload"]["payment"]["entity"]
        provider_order, payment_id = payment["order_id"], payment["id"]
        if (
            not isinstance(provider_order, str)
            or not isinstance(payment_id, str)
            or not payment_id.startswith("pay_")
            or not payment_id[4:].isalnum()
        ):
            raise ValueError("Invalid IDs")
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(422, "Invalid webhook event.")
    order = db.scalar(
        select(m.PaymentOrder).where(m.PaymentOrder.provider_order_id == provider_order, m.PaymentOrder.provider == "razorpay")
    )
    if not order or order.institution_id != config.payment_institution_id:
        raise HTTPException(404, "Payment order not found.")
    # Serialize duplicates with the same lock order as browser verification.
    db.scalar(select(m.FeeInvoice).where(m.FeeInvoice.id == order.invoice_id).with_for_update())
    event_id = "captured:" + payment_id
    if db.scalar(select(m.PaymentWebhook.id).where(m.PaymentWebhook.event_id == event_id)):
        return {"ok": True, "duplicate": True}
    verify_capture(db, order, payment_id)
    db.add(m.PaymentWebhook(institution_id=order.institution_id, event_id=event_id, order_id=order.id, event_type="payment.captured"))
    db.commit()
    return {"ok": True}


class ReconcileInput(Strict):
    payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]+$", max_length=100)


@router.post("/orders/{order_id}/reconcile")
def reconcile(order_id: str, body: ReconcileInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    order = scoped(db, m.PaymentOrder, user, order_id)
    payment_config(user.institution_id)
    if order.provider != "razorpay":
        raise HTTPException(422, "Only gateway payments can be reconciled.")
    payment = gateway("GET", "payments/" + body.payment_id)
    provider_id = payment.get("order_id", "")
    if not isinstance(provider_id, str) or not provider_id.startswith("order_") or not provider_id[6:].isalnum():
        raise HTTPException(422, "Invalid gateway order.")
    provider_order = gateway("GET", "orders/" + provider_id)
    if (
        provider_order.get("receipt") != order.id
        or provider_order.get("amount") != order.amount_paise
        or provider_order.get("currency") != "INR"
    ):
        raise HTTPException(422, "The provider receipt does not belong to this invoice.")
    order.provider_order_id = provider_id
    verify_capture(db, order, body.payment_id)
    audit(db, user, "payment.reconciled", order.invoice_id)
    db.commit()
    return {"ok": True}


class VoidInput(Strict):
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/{invoice_id}/void")
def void(invoice_id: str, body: VoidInput, user=Depends(current_user), db: Session = Depends(get_db)):
    require(user, ADMINS)
    invoice = invoice_access(db, user, invoice_id)
    db.refresh(invoice, with_for_update=True)
    if invoice.status != "unpaid" or db.scalar(select(m.PaymentOrder.id).where(m.PaymentOrder.invoice_id == invoice_id)):
        raise HTTPException(
            409, "Only an unpaid invoice without a payment order can be voided. Contact finance for payment reconciliation."
        )
    invoice.status = "void"
    audit(db, user, "fees.voided", invoice.id, {"reason": body.reason})
    db.commit()
    return {"ok": True}


@router.get("/receipts/{order_id}")
def receipt(order_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    order = scoped(db, m.PaymentOrder, user, order_id)
    invoice = invoice_access(db, user, order.invoice_id)
    if not order.receipt_number:
        raise HTTPException(404, "A verified receipt is not available yet.")
    audit(db, user, "payment.receipt_downloaded", invoice.id)
    db.commit()
    row = invoice_view(db, invoice)
    content = (
        "CampusMind AI · "
        + ("DEMONSTRATION RECEIPT — NO MONEY COLLECTED" if order.receipt_number.startswith("TEST-") else "PAYMENT RECEIPT")
        + f"\nReceipt: {order.receipt_number}\nInstitution: {db.get(m.Institution, user.institution_id).name}\nStudent: {row['student']}\nRegistration: {row['roll_no']}\nFee: {row['title']}\nTerm: {row['term']}\nINR: {order.amount_paise / 100:.2f}\nDate (UTC): {order.settled_at}\nProvider: {order.provider}\nPayment reference: {order.provider_payment_id}\n"
    )
    return Response(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{order.receipt_number}.txt"'},
    )
