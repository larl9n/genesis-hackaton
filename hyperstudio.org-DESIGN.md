# Hyperstudio — dot-matrix atelier

## Overview

A near-black technical atelier with warm sand annotations, soft grotesk headlines and monospaced operational labels. The atmosphere combines early-computer graphics with polished metallic controls and cinematic presentations of finished work. It suits specialist products and expert services that can let visual proof carry much of the story; text stays compact while the image sequence is expansive.

### Essentials

- A human headline above a machine-made gesture: regular 63px/66px grotesk type, -0.7px tracking, centered within 755px, above a full-width white-on-black dot-matrix sculpture.
- The page behaves like a continuous exhibition rail: 850px centered content, 1px #212121 vertical edges, square media panels around 850×486px, and faint horizontal rules extending past the column.
- Conversion controls resemble little silver keys: 40px outer height, 10px outer corners, a 2px inset with 20px corners and opposing gray gradients; secondary controls are 41px charcoal keys with 9px corners.
- Color is annotation rather than atmosphere: almost all page chrome is #080808, #101010 and gray; sand #e7c59a is confined to 14px mono section labels and small outline icons. Stronger hues belong inside the work imagery.
- Technical labels interrupt soft typography: Input capitals at 13.5px/20px on actions and 17.5px/23px on capabilities, against Aeonik paragraphs at 17px/22px.
- The ending is a compact invitation, not a giant slogan: a 153px-high rail-bound panel with 23.3px/25px copy and a silver key, followed by a small centered contact sentence. Include a restrained text-fade editorial panel as a second signature device.

## Colors

### Accent

| Name | Value | Token | Roles | Use |
| --- | --- | --- | --- | --- |
| Sand annotation | `#e7c59a` | `--color-sand` | text, accent | Section markers and small capability icons; not a broad page fill. |

### Neutral

| Name | Value | Token | Roles | Use |
| --- | --- | --- | --- | --- |
| Control ink | `#000000` | `--color-black` | text, background | Primary action text and monochrome graphic backing. |
| Near black | `#080808` | `--color-canvas` | background | Continuous page canvas; also the source hue of the 60% translucent fixed header. |
| Raised black | `#101010` | `--color-panel` | surface | Editorial and closing panels, subtly lighter than the canvas. |
| Charcoal key bottom | `#1d1d1d` | `--color-key-bottom` | surface | Bottom of secondary-button gradient. |
| Rail gray | `#212121` | `--color-rule` | border, surface | Thin exhibition rails and visible 10% white availability badge backing. |
| Charcoal key top | `#252525` | `--color-key-top` | surface | Top of secondary-button gradient. |
| Footer gray | `#888888` | `--color-muted` | text | Low-emphasis footer sentence. |
| Body gray | `#9c9c9c` | `--color-body` | text | Visible result of 60% white over the canvas for capability descriptions. |
| Contact gray | `#a3a3a3` | `--color-email` | text, link | Secondary contact line. |
| Silver inset top | `#b5b5b5` | `--color-inset-top` | surface | Top of the inner primary-button gradient. |
| Silver shell bottom | `#c0c0c0` | `--color-silver-bottom` | surface | Bottom of the outer primary-button gradient. |
| Support gray | `#c1c1c1` | `--color-support` | text | Visible result of 75% white over the canvas for lead and process copy. |
| Silver edge | `#c5c5c5` | `--color-control-edge` | border | Primary-button inset hairline. |
| Silver shell top | `#cfcfcf` | `--color-silver-top` | surface | Top of the outer primary-button gradient. |
| Category gray | `#dadada` | `--color-caption` | text | Monospaced category captions beside project names. |
| Silver inset bottom | `#e4e4e4` | `--color-inset-bottom` | surface | Bottom of the inner primary-button gradient. |
| Soft white | `#f3f3f3` | `--color-heading` | text | Headlines, labels and dark-button text. |
| Control white | `#ffffff` | `--color-white` | surface, link | Primary control base and footer links. |

## Current font — Inter 4.1

The user supplied Inter-4.1.zip and selected Inter as the free replacement. The project
bundles web/InterVariable.woff2 unchanged, with its SIL OFL license. Inter replaces the
Helvetica stack below; retain hero 900, headings 700, body/navigation 400, tight tracking,
and existing rails/colors. Optical sizing is automatic. No system installation is needed.

## Earlier project typography override — 14 November 2026

The user's latest direction overrides the original regular Aeonik recipes below for this project:
Helvetica Now Display for prose, navigation, and headings; hero weight 900, other headings 700,
tracking approximately −0.035em to −0.055em, heading line-height 1–1.08. Body and navigation
remain weight 400 with readable body leading. Technical IDs, JSON, and operational annotations
retain monospace. Rails, colors, dot sculpture, and silver controls remain as specified.

The user confirmed that font files are not available yet. CSS uses local Regular/Bold/Black
faces, then Helvetica Neue/Helvetica/Arial fallbacks. This is not bundled Helvetica Now Display
and does not promise identical type on other devices. When licensed webfont files are supplied,
add the corresponding same-origin WOFF2 sources and explicit static routes; verify Cyrillic,
all three weights, mobile wrapping, and the packaged wheel. Do not fetch arbitrary font copies.

## Typography (original reference)

- **Aeonik** — All prose, headings and project names. Clean geometric grotesk, rounded bowls and open proportions, almost entirely regular weight. If unavailable, use **Inter**. Use weight 400 and preserve tight headline tracking. Font stack: "Aeonik", "Inter", sans-serif.
- **Input** — Navigation, action labels, section markers and technical captions. Pragmatic monospaced lettering with a lightly engineered texture. If unavailable, use **IBM Plex Mono**. Use regular 400; retain compact sizes and uppercase labels. Font stack: "Input", "IBM Plex Mono", Arial, sans-serif.

| Recipe | Font | Weight | Size | Line height | Tracking | Use |
| --- | --- | --- | --- | --- | --- | --- |
| display | Aeonik | 400 | 63px | 66px | -0.0111em | Centered opening promise, usually two lines. |
| heading-lg | Aeonik | 400 | 44px | 1.068 | -0.0068em | Left-aligned capability and process section headings. |
| heading-editorial | Aeonik | 400 | 34px | 1.029 | normal | Centered heading inside the editorial panel. |
| closing | Aeonik | 400 | 23.3px | 1.073 | normal | Compact closing invitation. |
| contact | Aeonik | 400 | 22.6px | 1.106 | normal | Secondary closing contact line. |
| project-name | Aeonik | 400 | 21px | 0.952 | normal | Names in centered project headers. |
| lead | Aeonik | 400 | 18px | 1.222 | normal | One-sentence section support. |
| capability-label | Input | 400 | 17.5px | 1.314 | normal, uppercase | Capability grid titles. |
| editorial-body | Aeonik | 400 | 17.3px | 1.347 | normal | Longer paragraph in the fading editorial panel. |
| body | Aeonik | 400 | 17px | 1.294 | normal | Compact capability descriptions. |
| process-body | Aeonik | 400 | 16.7px | 1.275 | normal | Short process-step explanations. |
| category | Input | 400 | 16.5px | 1.212 | normal, uppercase | Technical category beside a project name. |
| step-label | Input | 400 | 16px | 1.25 | normal, uppercase | Numbered process headings. |
| footer | Aeonik | 400 | 16px | 1.375 | normal | Centered closing contact sentence and inline links. |
| eyebrow | Input | 400 | 14px | 1.5 | normal | Sand double-slash section markers. |
| navigation | Input | 400 | 13.7px | 1.2 | normal, uppercase | Compact fixed-header links. |
| action | Input | 400 | 13.5px | 1.48 | -0.022em, uppercase | Primary and secondary controls. |
| status | Input | 400 | 13px | 1.54 | normal, uppercase | Availability chip above the opening promise. |

**Notes:**

- Keep display headings regular, not bold. Only the two largest heading roles tighten tracking; mono labels otherwise use normal spacing except for the compact action recipe.
- Use contrasting type classes rather than a profusion of weights: conversational grotesk statements against uppercase operational mono labels.

## Layout

**Density:** Airy at section scale, compact inside controls and text groups; image panels form a nearly uninterrupted proof sequence.

### Spacing

| Value | Use |
| --- | --- |
| 7px | Eyebrow-to-heading gap. |
| 8px | Gap between paired hero actions. |
| 10px | Section-heading support gap and process title-to-description gap. |
| 16px | Project name/category row gaps. |
| 20px | Page side padding outside centered containers. |
| 24px | Project icon-to-caption spacing. |
| 30px | Editorial heading-to-paragraph separation. |
| 35px | Process-step group spacing and footer bottom padding. |
| 40px | Capability-cell horizontal padding. |
| 50px | Closing panel vertical padding. |
| 65px | Editorial panel top padding. |
| 130px | Major text-section lead-in and opening text start. |

### Containers and grids

- **Exhibition rail**: max width 850px · side padding 20px. Centered shared alignment for fixed navigation, text sections, work panels and closing bands.
- **Hero text**: max width 755px. Centered opening headline within the wider rail.
- **Capability grid**: max width 850px · 2 columns · gap 0px. Two-by-two shared-line matrix; cells approximately 427px wide, not separated floating cards.
- **Project caption**: max width 740px · gap 24px. Centered icon above a project name/category row.
- **Process split**: max width 850px · 2 columns. Promise and action on the left; narrow numbered rail and 348px step descriptions on the right.

## Corner radius

| Element | Radius |
| --- | --- |
| Primary shell | 10px |
| Primary inset | 20px |
| Secondary key | 9px |
| Availability chip | 4.5px |
| Project icon tile | 8px |
| Exhibition panels | 0px |

## Surfaces and depth

### Surfaces

#### Canvas · level 0

**Use:** Continuous page backing.

**CSS:** `background: #080808`

#### Rail panel · level 1

**Use:** Editorial and closing content grouped in the exhibition column.

**CSS:** `background: #101010; border-left: 1px solid #212121; border-right: 1px solid #212121; border-radius: 0px`

**Observed:** Flat, square panels distinguished by a small luminance change, not elevation.

**Transfer:** Keep different content bands on the same continuous side rails.

#### Fixed glass header · level 2

**Use:** Persistent top navigation.

**CSS:** `background: rgba(8, 8, 8, 0.6); backdrop-filter: blur(8px); height: 56px; position: fixed; top: 0px`

**Observed:** Full-width translucent backing with its inner content constrained to the exhibition rail.

#### Fading editorial text

**Use:** A restrained long-form teaser ending in an action.

**CSS:** `background-image: linear-gradient(rgba(242, 242, 242, 0.85), rgba(66, 66, 66, 0.19) 85%, rgba(50, 50, 50, 0.13) 94%, rgba(16, 16, 16, 0)); background-clip: text; -webkit-text-fill-color: transparent`

**Observed:** The paragraph dims toward its bottom while the button below stays fully legible.

**Transfer:** Apply only to teaser text that has a separate accessible full-reading destination, not essential instructions.

## Components

### Fixed navigation

**Use:** Persistent orientation and conversion.

**CSS:** `height: 56px; padding: 8px 0px; max-width: 850px; display: flex; justify-content: space-between; align-items: center; gap: 35px`

**Text style:** `navigation` — Input 400 · 13.7px/1.2 · uppercase

**Observed:** Wordmark at left, a thin vertical separator, three inline destination links with 25px spacing, then a silver conversation key at right. A tiny superscript novelty tag marks one destination.

**States:** Declared: hover opacity 0.8 on destination links; focus-visible unknown.

### Primary button

**Use:** Start, inquiry and form actions.

**CSS:** `background: linear-gradient(#cfcfcf, #c0c0c0); color: #000000; border-radius: 10px; height: 40px; display: inline-flex; align-items: center`

**Text style:** `action` — Input 400 · 13.5px/1.48 · tracking -0.022em · uppercase

**Observed:** A silver outer shell encloses the Primary button inset. The label sits before a small diagonal arrow; the header variant instead starts with a circular monochrome profile emblem.

**States:** Declared: hover background-image linear-gradient(rgb(222, 222, 222), rgb(222, 222, 222)); focus-visible unknown.

### Primary button inset

**Use:** Recessed face inside every silver action.

**CSS:** `background: linear-gradient(#b5b5b5, #e4e4e4); border: 1px solid #c5c5c5; border-radius: 20px; margin: 2px; height: 36px; display: flex; align-items: center; justify-content: center`

**Text style:** `action` — Input 400 · 13.5px/1.48 · tracking -0.022em · uppercase

**Observed:** The rounded inner face runs almost to the outer edge; label padding is asymmetric to make space for the arrow.

### Secondary button

**Use:** Proof browsing and secondary editorial actions.

**CSS:** `background: linear-gradient(#252525, #1d1d1d); color: #f3f3f3; border-radius: 9px; height: 41px; display: inline-flex; align-items: center; justify-content: center`

**Text style:** `action` — Input 400 · 13.5px/1.48 · tracking -0.022em · uppercase

**Observed:** A low-contrast charcoal key with a downward arrow, paired with the silver action or centered below an editorial teaser.

**States:** Declared: hover opacity 0.9; focus-visible unknown.

### Availability chip

**Use:** Small timely status above the opening headline.

**CSS:** `background: rgba(255, 255, 255, 0.1); border-radius: 4.5px; height: 28px; padding-left: 3.3px; display: inline-flex; align-items: center; color: #f3f3f3`

**Text style:** `status` — Input 400 · 13px/1.54 · uppercase

**Observed:** A tiny green status dot precedes a single monospaced line; the chip is subordinate to the headline.

**States:** Declared: hover opacity 0.8; focus-visible unknown.

**Transfer:** Use only truthful capacity or availability information; a release-status statement can serve the same role.

### Capability cell

**Use:** Compact explanation of a benefit or capability.

**CSS:** `padding: 33px 40px 45px; border-radius: 0px`

**Text style:** `capability-label` — Input 400 · 17.5px/1.314 · uppercase

**Observed:** Small sand outline icon, then a 19px gap to the uppercase title and an 11px gap to body copy. Cells share a faint matrix backing rather than separate outlines.

**Transfer:** Give each cell a concise functional heading and one sentence describing the outcome.

### Project caption

**Use:** Introduce a visual proof chapter.

**CSS:** `display: flex; flex-direction: column; align-items: center; gap: 24px; max-width: 740px`

**Text style:** `project-name` — Aeonik 400 · 21px/0.952

**Observed:** A 40px rounded icon tile sits above a name and mono category, separated by a thin vertical rule and 16px gaps. The name/category row is centered above the square-edged media stack.

### Media panel

**Use:** Stack visual proof at exhibition scale.

**CSS:** `max-width: 850px; border-left: 1px solid #212121; border-right: 1px solid #212121; overflow: clip; border-radius: 0px`

**Observed:** Most media occupies about 850×486px; occasional paired portrait panels divide the width evenly. Edges align exactly from image to image.

**Transfer:** Alternate a large graphic, a construction/detail view and a real-world application without wrapping them in extra cards.

### Closing invitation

**Use:** Last substantial conversion band.

**CSS:** `background: #101010; border-left: 1px solid #212121; border-right: 1px solid #212121; max-width: 850px; padding: 50px 85px; display: flex; justify-content: space-between; align-items: center; gap: 15px`

**Text style:** `closing` — Aeonik 400 · 23.3px/1.073

**Observed:** A short benefit-led invitation and a gray contact line occupy the left; a single silver key sits on the right.

### Footer contact

**Use:** A small human endpoint below the final band.

**CSS:** `color: #888888; text-align: center; padding: 30px 20px 35px`

**Text style:** `footer` — Aeonik 400 · 16px/1.375

**Observed:** One muted question with white inline email and direct-message links. No multicolumn sitemap or large legal block.

## Imagery and graphics

### Dot-matrix gesture

**Use:** Signature full-bleed opening art beneath the headline.

**Observed:** Two reaching hands meet across a central black gap, rendered in horizontal rows of white diamond-like dots. The image extends slightly beyond both viewport edges and occupies roughly the lower half of the opening; there is no colorful glow or card frame.

**Transfer:** Render a product-relevant gesture, tool silhouette or paired abstract forms using the same white dot field. The minimum equivalent is a recognizable silhouette or two sculptural arcs in ordered dots, not random visual noise.

**Build:** Use an SVG mask of the chosen silhouette over a black field. Fill it with staggered rows of white diamonds on roughly 7px centers; vary diamond size from about 1px to 5px using underlying grayscale luminance. Let highlights merge into bright rows, keep shadow rows sparse, and leave a central negative-space gap. Size the composition around 1498×475px at a 1440px viewport and clip the outer edges.

### Extended drafting rails

**Use:** Signature structure around capabilities, proof chapters and the closing bands.

**Observed:** Dim vertical lines lock to the 850px column; horizontal rules overshoot into the side gutters and fade at their extremities. The effect is an engineering drawing, not a visible tiled grid.

**Transfer:** Carry the same rails through the page even when proof changes from brand work to product demonstrations.

**Build:** Draw 1px vertical #212121 rules at the centered column edges. Add horizontal 1px SVG lines spanning about 1290px around major panel boundaries; use an opacity mask fading from transparent at the ends to full opacity within the 850px column. Extend the vertical lines above and below selected blocks and fade them away. Keep all lines subordinate to text.

### Cinematic proof boards

**Use:** Dominant long-form proof area.

**Observed:** A sequence of finished identity scenes: a luminous Earth horizon on black, a teal-black hazy logo stage, bright construction drawings with thin guides, brushed-metal or printed-card mockups, and silver light streaks. Individual boards fill the rail width; occasional saturated red or cool blue appears inside the artwork while the surrounding interface stays black.

**Transfer:** For software, pair a restrained dark product render with light detail boards and realistic application scenes. For physical products, use close-up material photography, assembly diagrams and contextual use. Minimum quality is a crisp product silhouette on a carefully lit backing plus a legible detail board; avoid low-quality synthetic mockups.

### Icons

**Observed:** Capability icons are small sand line drawings around 23px; action arrows are 18–20px and match the label color. Project marks sit in 40px rounded tiles. The header conversion key includes a monochrome profile silhouette.

**Transfer:** Use simple technical outline symbols at the same optical weight, not colorful emoji or oversized filled illustrations.

## Section recipes

How recurring sections are built.

### First screen: Promise above a dot sculpture

**Observed:** A 56px Fixed navigation sits over the black Canvas. The centered text group starts around 130px down: Availability chip, 16px separation, a regular two-line 63px/66px display promise within 755px, then paired Primary button and Secondary button 23px below with an 8px gap. The Dot-matrix gesture stretches edge to edge beneath the controls, roughly 475px high. Layers are black field, white dot art, centered text and actions, then the fixed header. Within the first 900px the whole promise, chip, both controls and main gesture are visible; the next section's label begins at the lower boundary. There is no separate introductory paragraph.

**Transfer:** Use a direct outcome-and-audience promise and a dot-rendered form meaningful to the new product. When no photography is available, make the ordered-dot silhouette itself the main object. A focused secondary landing page can shorten the promise and proof sequence while retaining this same first-screen hierarchy.

**Avoid:** Do not replace the white dot sculpture with a generic dashboard card, add a long hero paragraph, or put the headline in a left-hand split layout.

**Text style:** `display` — Aeonik 400 · 63px/66px · tracking -0.0111em

### Annotated capability matrix

**Observed:** An eyebrow beginning with double slashes sits 7px above heading-lg; a lead line follows after 10px. The heading aligns to the exhibition rail, not the outer extent of its drafting-line backing. Capability cells form a two-column, two-row matrix below.

**Transfer:** Use the matrix for a small set of distinct outcomes rather than an exhaustive feature inventory.

**Text style:** `heading-lg` — Aeonik 400 · 44px/1.068 · tracking -0.0068em

### Visual proof chapter

**Observed:** Project caption introduces an uninterrupted Media panel sequence. Large square-edged images share continuous side rails, with almost no vertical gaps. Extended drafting rails introduce and close chapters.

**Transfer:** Create a chapter around a concrete use case or result and show it from several distances: overall result, detailed mechanics, contextual use.

### Split process explanation

**Observed:** The 850px Process split places a sand eyebrow and large multiline heading at left, with short reassurance and a Secondary button near the bottom. At right, small two-digit numbers align with uppercase step labels and compact descriptions; step groups have 35px gaps.

**Transfer:** Explain adoption, operation or collaboration using the same editorial-versus-operational split; use only the steps necessary for the new offer.

**Text style:** `heading-lg` — Aeonik 400 · 44px/1.068 · tracking -0.0068em

### Fading editorial panel

**Observed:** A Rail panel contains a centered heading-editorial, a paragraph 30px below and a centered Secondary button. Inner padding is 65px top, 95px sides and 63px bottom. Fading editorial text dims the lower lines, making the fully opaque action stand out.

**Transfer:** Use this device for a point of view or deeper explanation with a full reading destination, rather than forcing every page to tell a founder story.

**Text style:** `heading-editorial` — Aeonik 400 · 34px/1.029

### Rail-bound close

**Observed:** Closing invitation is a shallow, 153px-high band with a two-line text group opposite a Primary button. Extended drafting rails continue beyond it. Footer contact ends the page as a single centered line with 35px bottom breathing room.

**Transfer:** End with a simple next step and a human alternative contact route; the final visual emphasis remains the small silver key, not a billboard-sized closing headline.

**Text style:** `closing` — Aeonik 400 · 23.3px/1.073

## Page flow

**Storyline:** Direct promise → compact capabilities → sustained visual proof → explanation of working method → point of view → human invitation.

### A specialist marketing landing page that earns trust primarily through visual output

1. **Promise** — Centered two-line proposition above monochrome dot art and a paired action row.
2. **Capabilities** — Annotated heading and concise shared-line capability matrix.
3. **Visual proof** — Repeated captioned chapters with full-width media stacks and drafting rails.
4. **Objection handling** — Split explanation of the method with numbered steps and a secondary action.
5. **Point of view** — A fading editorial teaser in a subtly raised black panel.
6. **Closing call** — Compact invitation band and an understated contact sentence.

**Transfer:** Let proof occupy more space than promotional prose. Adapt the number and order of chapters to the product; retain the monochrome gesture, rail structure, material controls and compact ending.

## Writing

Confident and commercially direct, with a small-studio human warmth. Claims are short and ambitious; practical explanations soften them with plain language.

**Do not copy:** Do not reuse the studio name, project identities, artwork, email address, capacity counts, sector claims, awards, guarantees or founder history. Replace all proof and claims with substantiated information for the new product. The examples below show the pattern only; write new copy for the new product.

- **Addressing the reader:** Use we for the team and you or your for the customer; connect capabilities to the reader's outcome.
- **Rhythm:** Short declarative headlines, uppercase functional labels, one-sentence descriptions and clipped three-part statements. Longer prose is reserved for the editorial teaser.

| Role | Pattern | Typical length | Examples of the pattern |
| --- | --- | --- | --- |
| Opening promise | State quality, deliverable and audience in one direct sentence. | 6–10 words | “World-class branding and websites for startups.” |
| Section headline | Pair present action with future advantage, or use three punctuated attributes. | 3–7 words | “Invest Today, Stand Out Tomorrow”<br>“Unique. Strategic. Timeless.” |
| Capability description | Name the practical outcome without a technical digression. | 10–16 words | “Easy to remember and distinctive logos, giving your brand a unique identity.” |
| Process reassurance | Conversational and low-friction, with a short second fragment. | 8–14 words | “It all begins with a no-stress chat. Without compromises.” |
| Action | Brief imperative, uppercase in the interface. | 2–4 words | “START NOW”<br>“VIEW WORK”<br>“FILL THE FORM” |
| Closing invitation | Delegate the difficult part so the reader can focus on the result. | 8–12 words | “Leave design to us, focus on growth.” |

**Words and phrasing to use:** stand out; built for; distinctive; strategic; launch; no-stress; focus on; gets it

**Avoid:** synergistic ecosystem; revolutionize everything; corporate mission boilerplate; overlong technical acronyms in headlines

**Rules:**

- Tie abstract quality words to visible proof nearby.
- Keep action language literal; the button should name its next step.
- Use double-slash section labels as short signposts, not full sentences.
- Avoid inflating every description into a headline; keep supporting copy one or two lines.

## Do's and Don'ts

### Do

- Keep the main headline at 400 weight and 63px/66px on desktop.
- Align navigation, proof and closing panels to one 850px rail.
- Use 1px #212121 edges and square panel corners.
- Construct the silver key from an outer gradient and a separately rounded 2px inset.
- Use 14px sand mono markers and 23px outline icons as small warm accents.
- Let the proof media occupy whole 850px-wide boards, not thumbnails.
- Finish with the 23.3px closing role and a small 16px contact line.

### Don't

- Do not turn the silver 40px keys into flat sand pills.
- Do not add floating shadows to the rail panels; the surface system is flat.
- Do not make all text white; distinguish headings, support, body and contact gray.
- Do not give each capability its own rounded card and 24px gutters; it is a continuous matrix.
- Do not spread saturated gradients across the marketing canvas; reserve stronger color for imagery.
- Do not style operational labels in the grotesk or long prose in the mono.
- Do not replace the final compact contact sentence with a dense multicolumn sitemap.

## Motion and responsive

### Motion

**Observed:**

- Actions declare opacity transitions of 0.2s. Secondary keys use hover opacity 0.9; navigation and status links use 0.8. Primary shells declare a flat light-gray hover gradient.
- No matched keyframe animations are declared.

**Transfer:**

- Keep hover changes subordinate to the material construction of the keys; do not add large travel or scale effects to the action row.

**Unknown:**

- Timing and behavior of the dot artwork or any scroll-driven effects are not established.

### Responsive

**Observed:**

- Width breakpoints are declared at 479px, 480px, 767px and 991px; the measured composition is desktop.

**Transfer:**

- Preserve the centered headline over the dot graphic at narrow widths. Reduce type enough to avoid clipping, retain black negative space and clip the graphic rather than shrinking it into a card.
- Collapse the capability matrix and process split into a single reading column when space is insufficient. Keep the drafting rails aligned to the new content edges and stack the closing key below its text.

**Unknown:**

- Exact mobile type sizes, navigation replacement and art positioning are not established.

## How to use this guide

1. Start from the Essentials and the first-screen recipe; where the guide offers variants, use the default named for a new marketing page.
2. Plan the page before building: map your content onto the section recipes and page flow, then check the plan against the Do's and Don'ts.
3. Build with the tokens and component specs; recreate signature graphics with their build recipes instead of generic decoration, and use the named font substitutes if a font is unavailable.
4. Render the page at desktop and mobile widths, compare it with the Essentials and the Don'ts, and fix the differences before you finish.
