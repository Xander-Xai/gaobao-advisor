# OG Image Specification for WeChat Sharing

## Overview

When users share the gaoBao AI advisor link on WeChat, QQ, or other social platforms, the
Open Graph (OG) image is displayed as a preview card. This document describes the design
specification for creating that image.

## Technical Requirements

| Property | Value |
|----------|-------|
| Dimensions | 1200 x 630 px (OG standard) |
| Format | PNG (preferred) or JPG |
| Max file size | < 1 MB (WeChat truncates larger images) |
| Color space | sRGB |
| Filename | `og-image.png` |
| Deployment | Place at the URL set by `OG_IMAGE_URL` env var |

## Layout

```
+------------------------------------------------------+
|                                                      |
|   [gaoBao Logo]                                      |
|                                                      |
|   gaoBao AI                                          |
|   高考志愿顾问                                        |
|                                                      |
|   "基于 3000+ 院校数据，免费帮你科学填报志愿"           |
|                                                      |
|   [QR Code Placeholder]      [2026 高考季]           |
|                                                      |
+------------------------------------------------------+
```

### Zones

1. **Top-left**: Logo icon (graduation cap emoji or brand mark), 60px padding from edges.
2. **Center-left**: Brand name "gaoBao AI" in bold, subtitle "高考志愿顾问" below.
3. **Center**: Tagline in medium weight -- the app's value proposition.
4. **Bottom-right**: "2026 高考季" badge or year indicator.
5. **Bottom-left** (optional): QR code placeholder linking to the app URL.

## Color Palette

Match the app's existing theme colors:

| Element | Color | Hex |
|---------|-------|-----|
| Background | Light blue gradient (start) | `#EFF6FF` |
| Background | Light green gradient (end) | `#F0FDF4` |
| Primary text | Dark navy | `#1F2937` |
| Accent / brand blue | Primary blue | `#1A56DB` |
| Secondary text | Gray | `#6B7280` |
| Badge background | Warm amber | `#FEF3C7` |
| Badge text | Dark amber | `#92400E` |

## Typography

- **Brand name**: Bold, 48-60px, system font or Noto Sans SC Bold.
- **Subtitle**: Semi-bold, 32-40px.
- **Tagline**: Regular, 24-28px.
- **Badge text**: Bold, 18-20px.

## Design Tools

Recommended creation methods (pick one):

1. **Figma**: Create a 1200x630 frame, export as PNG.
2. **Python (Pillow)**: Use `PIL.Image` to generate programmatically.
3. **HTML + Screenshot**: Build in HTML, use Puppeteer/Playwright to capture at 1200x630.

## Deployment

1. Create the image following the spec above.
2. Host it at a publicly accessible URL (GitHub raw, S3, or CDN).
3. Set the `OG_IMAGE_URL` environment variable in Streamlit Cloud or `.env`:
   ```
   OG_IMAGE_URL=https://your-cdn.com/og-image.png
   ```
4. Verify by sharing the app URL in WeChat -- the preview card should show the image.

## Verification

After deployment, test the OG tags with:

1. **WeChat**: Paste the URL in a WeChat chat, check the preview card.
2. **Facebook Sharing Debugger**: https://developers.facebook.com/tools/debug/
   (also validates og:image, og:title, og:description).
3. **WeChat JSSDK**: For advanced sharing customization, integrate WeChat JS-SDK
   (`updateAppMessageShareData` / `updateTimelineShareData`) if the domain is
   registered as a WeChat official account third-party platform.

## Notes

- WeChat's crawler respects standard OG tags. The `<meta>` tags injected via
  `st.markdown(unsafe_allow_html=True)` in app.py are parseable by WeChat's
  link preview generator.
- The `OG_IMAGE_URL` env var defaults to a GitHub raw URL placeholder.
  Update it once the actual image is created and deployed.
- For WeChat Work (企业微信) shares, the same OG tags apply.
