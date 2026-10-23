# Proofreading report: ISU-ARMAC website content

All 101 pages and 674 blog posts were checked during the move to Django CMS. Every correction lives in
`site_core/content_fixes.json` and is applied each time the import runs, so the live WordPress text is
untouched and any correction can be reversed by deleting its line.

## What was fixed automatically

| Problem | Where | Fix |
| --- | --- | --- |
| Words broken by an earlier automated rewrite ("finded", "liftd", "digd", "steerd", "solveing", "findy", "tripr", "Open uping") | 60+ blog posts | Restored to found, elevated, dug, navigated, unraveling, discovery, rider, unlocking |
| Missing dashes that glued words together ("worrywe're", "safeeven", "valueit", "elseand", "carriernot") | 6 posts | Words separated with correct punctuation |
| Notes meant for the writer published as visible text ("Header image metadata for your publishing team…", "IPTC metadata…", "Alt text: …", image-description data) | about 60 posts | Removed |
| The AI writer talking about a missing link ("The internal link provided in the brief appears as [object Object]…") | 2 posts | Paragraph removed |
| "[object Object]" printed in place of a link | 3 posts | Replaced with "ISU-ARMAC" |
| Raw ChatGPT citations, e.g. `([geico.com](https://…?utm_source=openai))` | 4 posts | Turned into normal links, tracking tag removed |
| "… vocab to learn:" labels over internal link lists | 26 posts | Relabeled "Related reading" (links kept) |
| A raw image file address pasted as a paragraph | 1 post | Removed |
| Lorem ipsum placeholder text | Life & AD&D page (live site) | Replaced with new copy (please review, see below) |
| Doubled words ("due due", "a a", "understand understand") | 5 posts | Fixed |
| Spelling (pharmacists, devastating, assistant, losses, mishaps, in-depth and others) | posts | Fixed |
| Space before commas and periods ("California , we") | many pages and posts | Fixed |
| Agency name written 7 different ways ("ISU Armac", "ISU – Armac", "ISU-Armac", "Armac Insurance Agency", "ARMAC Insurance Services", "ISU Insurance Services" when it meant the agency) | most pages and posts | Standardized to **ISU-ARMAC** in body text. SEO page titles were left as they are so search rankings are not disturbed. "ISU Insurance Services" is kept where it means the national network. |
| Grammar, wrong words and British usage on the 84 converted site pages (199 fixes, e.g. "Collision Deductive Waiver" → "Deductible", "waves your deductible" → "waives", "piece of mind" → "peace of mind", "police profile" → "policy profile", "Group Vison" → "Group Vision", "Umbrella Insurancee", "emotional damage" → "emotional distress", "obligers" → "obligors", "cover" → "coverage") | 60+ pages | Fixed |
| A page section repeated twice in a row | Individual Medical (private client) | Second copy removed |

## Needs your decision (not changed)

1. **Life & AD&D page:** the live page is only lorem ipsum. I wrote new copy (what group life and AD&D are, why employers offer them, how ISU-ARMAC helps, and 3 FAQs). Please approve or edit it.
2. **Medicare Supplement page:** says "Medicare can help cover the differences…" when it means Medicare *supplements* cover what Medicare doesn't. That is a factual change, so please confirm.
3. **Glossary, liability definition:** says liability covers "negligent or intentional acts." Liability insurance generally excludes intentional acts. A reviewer suggested "unintentional." Please confirm the intended definition.
4. **Home Insurance page:** suggests an *umbrella* policy for flood or earthquake damage. Umbrella policies don't cover that (the page's own FAQ says those need separate policies). Suggested wording: "a separate flood or earthquake policy."
5. **Home Insurance page:** "you pose less of a risk to lenders" probably means *insurers*.
6. **Individual Medical page:** HDHP limits shown for 2025 ($1,600 / $8,050) look like the 2024 IRS figures. Please verify.
7. **Testimonials:** client quotes were kept in the clients' own words. Only a split word ("knowledge able") was fixed. Small slips such as "exceeds in customer service" and "Just you to know that!" were left alone. Tell me if you'd like them tidied.
8. **Our Team:** Rebecca Scharnberg has no job title on the current site.
9. **Nevada contact page:** the current site lists the location as "Somewhere in Nevada." It has been left off the new design until a real address is provided.
10. **Odd blog address:** one post lives at `/slugbusiness-owners-policy-cost-guide-2026/` (a "slug" prefix was left in). The URL was kept so existing links work. It can be renamed with a redirect if you want.
11. **Hospital programs:** the new hospital page leaves out the "Programs" section until you give me the program names.
12. **Two images were already broken** on the live site and are missing from the new one too: `2021/08/105_Ox5pbhgK4M…-1024x656.jpg` and `2021/08/owtzllboSTx…-1024x258.png`.

## How the check was done

- A spellchecker ran over all 1.8 million words. Real errors were separated from insurance jargon and brand names by hand.
- The 84 site pages converted from WordPress were each read in full for grammar, word choice and brand consistency.
- Blog posts were checked automatically for spelling, doubled words, placeholders and leftover writer notes, but were not read line by line (1.76 million words). The patterns above cover the systematic problems found.
