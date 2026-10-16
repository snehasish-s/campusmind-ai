import type { Metadata } from "next";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./globals.css";
import { Providers } from "@/components/providers";
export const metadata: Metadata = {
  title: {
    default: "CampusMind AI — A connected campus. A clearer future.",
    template: "%s | CampusMind AI",
  },
  description:
    "CollegeOps and PlacementOS: institution operations and student placement, connected. Locally runnable and built for engineering institutions.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
