import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "CampusMind AI",
    short_name: "CampusMind",
    description: "Your connected campus workspace",
    start_url: "/app/campus",
    display: "standalone",
    background_color: "#F8FAFC",
    theme_color: "#0B1220",
    icons: [
      {
        src: "/campus-icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
