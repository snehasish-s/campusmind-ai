import { Network } from "lucide-react";
export function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark">
        <Network size={22} strokeWidth={1.8} />
      </div>
      <span>
        CampusMind<em>AI</em>
      </span>
    </div>
  );
}
