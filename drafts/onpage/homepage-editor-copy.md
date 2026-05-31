# GV Skincare — Home page on-page copy (Wix Editor paste-doc)

Built 2026-05-31 from a live crawl + public-source research. Pair this with
`homepage-schema.json` (the API-lane structured data). Items marked **[CONFIRM]**
need a real value from you before they ship.

---

## 0 · Canonical NAP (use this exact block everywhere)

> **GV Skincare Center**
> 23410 Grand Reserve Dr, Suite 302, Katy, TX 77494
> (346) 257-4149 · info@gvskincare.com
> Tue–Sat, 9:00 AM–5:00 PM · By appointment only (closed Sun & Mon)

Pick **"GV Skincare Center"** as the one canonical name — it's what Google, Yelp,
Facebook, and Birdeye already use, so it matches the strongest external signals.

### NAP audit — inconsistencies found on the site today

| Field | Variants found | Fix to |
|---|---|---|
| **Name** | `GV SKINCARE` (title/footer), `GV Skincare` (schema), `GV Skin Care Center` (homepage body/about), `GV SKIN CARE Center` (Facebook), `GV SKINCARE CENTER` (Google/Yelp) | **GV Skincare Center** everywhere |
| **Street** | schema: `23410 Grand Reserve Drive` (no suite); footer: `23410 Grand Reserve Dr. Suite 302` | `23410 Grand Reserve Dr, Suite 302` |
| **Phone** | schema: `3462574149` (raw, no format); not a clickable link on page | display `(346) 257-4149`; schema `+1-346-257-4149`; add `tel:` link |
| **Hours** | absent from schema entirely; only prose on Contact page | add to schema + show on home page |
| **Schema** | duplicate `WebSite` node; bare `LocalBusiness` | single graph (see `homepage-schema.json`) |

---

## 1 · Hero / entity block

**H1 (replace `SKIN & BODY SPA`):**
> GV Skincare Center — Facial & Body Spa in Katy, TX

**Answer sentence (add directly under the H1, as real text):**
> GV Skincare Center is a bilingual facial and body spa in Katy, TX (Cinco Ranch),
> offering HydraFacial, dermaplaning, microneedling, chemical peels, PRP, and body
> contouring. Rated 4.9★ by 800+ clients. Book online or call (346) 257-4149.

*Keep this as live HTML text, not baked into the hero image/slider, or crawlers can't read it.*

---

## 2 · Services section (add text under each of the 4 tiles)

Right now the tiles are image links with no readable text. Add a one-liner under each:

- **Evaluation** — "New to GV? Start with a one-on-one skin evaluation in Katy. We
  analyze your skin and build a treatment plan matched to your goals — facials,
  peels, or microneedling."
- **Facial Treatment** — "Facials for every concern: HydraFacial, dermaplaning,
  chemical peels, microdermabrasion, acne and anti-aging facials, RF microneedling,
  PRP, and back facials. From $[CONFIRM]."
- **Body Treatment** — "Body contouring, ultrasonic cavitation, lymphatic drainage
  massage, body wraps and whitening, and bridal packages. From $[CONFIRM]."
- **Virtual Consultation** — "Can't come in yet? Get a personalized skincare plan
  online. We review your skin over video and recommend products and treatments —
  in English or Spanish."

---

## 3 · Reviews section ("From our clients")

Add, above the testimonials, a visible rating line that matches the schema:
> ⭐ 4.9 average from 800+ reviews on Google

Then for each testimonial show the **reviewer name + star rating** (not just the
quote). Ideally pull live from Google reviews so the on-page rating and the
`aggregateRating` in schema always match.

---

## 4 · FAQ section (new on the home page) — 6 Q&As

Add a visible FAQ block; these mirror the `FAQPage` schema word-for-word so the
rendered text and the markup agree. Lead each answer with the quotable sentence.

1. **Where is GV Skincare Center located?**
   23410 Grand Reserve Dr, Suite 302, Katy, TX 77494, in the Cinco Ranch area of
   Katy. We serve Katy, Cinco Ranch, Fulshear, Richmond, and west Houston, by
   appointment Tuesday–Saturday.
2. **What treatments does GV Skincare Center offer?**
   HydraFacial, dermaplaning, microdermabrasion, chemical peels, RF microneedling,
   microneedling, PRP, acne and anti-aging facials, back facials, body contouring,
   ultrasonic cavitation, lymphatic drainage massage, body wraps, and bridal packages.
3. **Do I need an appointment, and what are your hours?**
   Yes — by appointment only. Tuesday–Saturday, 9:00 a.m.–5:00 p.m., closed Sunday
   and Monday. Book online or call (346) 257-4149.
4. **How do I book an appointment?**
   Book online or call/text (346) 257-4149. Unsure which treatment fits? Start with
   an in-person evaluation or a virtual consultation.
5. **Do you offer payment plans?**
   Yes. We offer payment plan options to spread the cost of treatments and packages.
   See the Payment Plans page or ask when you book.
6. **¿Hablan español?**
   Sí. Atendemos en español e inglés. Gaby y el equipo te asesoran sobre el mejor
   tratamiento facial o corporal. Llama o escribe al (346) 257-4149.

---

## 5 · Contact / click-to-call

- Make the phone a tappable link in the header/hero: `tel:+13462574149` → shows `(346) 257-4149`.
- Show the canonical NAP block (section 0) in the footer on every page, identical wording.

---

## Open items (need your input before final push)

- **[CONFIRM] Price ranges** for the Facial and Body service tiles (and a HydraFacial
  starting price if you want it in the FAQ). Currently `priceRange: "$$"` as a placeholder.
- **[CONFIRM] Exact review count** to display + put in `aggregateRating` (used 4.9 / 856
  from Birdeye; the on-page number must match whatever we show, ideally the live Google count).
- **[OPTIONAL] Gabriela's full name** if you want a `Person`/`founder` node in the schema
  (reviews reference "Gaby"). Left out for now to avoid guessing.
- **Wix note:** Wix auto-injects its own `LocalBusiness` + `WebSite` schema. On push we
  either disable Wix's auto structured data for the home page or rely on `@id` de-duplication
  so we don't end up with two business nodes again.
