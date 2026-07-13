import { MetadataRoute } from "next";

// Explicit robots policy. Without this file the site shipped no robots.txt at
// all, so crawlers had no sitemap pointer and no guidance on the auth-gated
// surfaces. Allow everything public, point at the sitemap, and keep the
// signed-in account area + raw API out of the index.
export default function robots(): MetadataRoute.Robots {
  const baseUrl = "https://garl.ai";
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/account"],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
    host: baseUrl,
  };
}
