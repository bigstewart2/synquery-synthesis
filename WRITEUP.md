# Synquery Take-Home Writeup

## The goal

Today the client gets raw transcripts and has to mine them by hand. The goal here is that after Synquery runs a panel, the client opens one page that already answers their question, with every claim sourced, and pulls what they need straight into their deck. Three hour-long calls become slide-ready data instead of homework.

## What I assumed

- The interview guide already comes from the client's question. That's how Synquery works today.
- The interviews keep asking typed questions, rankings, 1 to 10 ratings, prices. That's what makes the Ratings and Numbers tab buildable.
- The client gives their question and a starting set of themes at kickoff.
  - This can stay light. They share their key questions, we propose a theme set back, they sign off. Some back and forth here is worth it. Early alignment on themes beats building the wrong structure, and the final structure stays subject to their confirmation.
- A human looks things over before anything goes out.

## What it includes

- **Themes and Quotes.** Every finding is a row, who said it, the theme, the takeaway, the verbatim quote. Filter by theme or expert and you have the raw material for a slide in seconds, with the client's themes kept visually separate from the ones we added.
- **Ratings and Numbers.** All the typed answers laid out as tables, the vendor ratings matrix, prices, commercial terms, loyalty and switching. This is where three separate conversations become one comparison.
- **Transcripts.** The full calls, cleaned and redacted. Every number and quote in the product clicks through to the exact moment here, which is what makes the rest of it defensible.
- **Coverage.** What this panel can and can't support, stated plainly. It keeps a claim the data can't back off the client's slide, and it points at which interviews to run next.
- **Summary.** Five claims a client might actually put on a slide, each with a verdict, supported, supported with caveat, or not supported by this panel, and a footnote written to paste under the slide.
- **Running through all of it, three principles.** Everything is cited. Everything is structured. Everything is comparable.

## The workflow it takes over

The middle of the client's workflow disappears. They go from mining transcripts to reviewing findings and building their deck.

| Step               | Today    | With this        |
|--------------------|----------|------------------|
| Run the interviews | Synquery | Synquery         |
| Pull themes        | Client   | Product          |
| Pull quotes, cite  | Client   | Product          |
| Build tables       | Client   | Product          |
| Compare interviews | Client   | Product          |
| Quality review     | Client   | Quick human pass |
| Build the deck     | Client   | Client, faster   |

## What a client couldn't build themselves

The client brings their **question** and their **starting themes**. The product pulls **its own themes** on top, clearly marked as ours, so they get value beyond what they asked for. That second part **compounds**. Synquery analyzes interviews **across many clients and projects**, so theme-pulling gets **smarter with volume** that no single client ever has. A client could wire up their own transcript parser. **They can't replicate the volume.**

## Where AI does the work, and where it's plain software

- AI handles the parts that need reading. Finding a rating or a price inside a conversational answer, matching a quote to a theme, wording a takeaway. Judgment work.
- Plain software handles the parts that have to be exactly right. Averages, counts, checking that a quote matches the transcript word for word, swapping employer names for placeholders. Ordinary code, same answer every run, nothing invented.
- The split exists because a language model can occasionally make things up and ordinary code can't. So nothing a model wrote ever becomes a number. Models find and phrase. Code counts and checks.
- Extracted data points are stored with their quote and timestamp, and every table is computed from them. Interview four updates every view without touching interviews one through three.

## Worth calling out

- It flags data problems instead of papering over them. A rating given as 9 out of 10 on a question asked 1 to 7 gets held out of the averages, not blended in.
- Every build re-checks every citation against the transcripts before anything renders. A broken link fails the build instead of reaching a client.

## The rollout, week by week

**Week 1, react.** Put the prototype in front of the team and one design partner. The question is blunt, would this help on a live project and what's missing. No heavy build until that answer is a yes. Engineering starts the ingestion and export plumbing in parallel.

**Week 2, train on history.** Run it across the past interviews we already have. We're sitting on a lot of them, so the theme library can get genuinely smart before any client sees it. Engineering builds the review workspace and the data layer, stable IDs on every data point so re-running extraction never breaks a citation a client already used.

**Weeks 3 and 4, sandbox.** A couple of design partners use it on real projects. A person signs off on everything before it reaches them, and every correction gets logged. Engineering walls each client's data off from the others before a second client's data ever enters the system.

**Week 5 and beyond, live and learning.** Roll out wider. The logged corrections become a running test set, so extraction and theme-pulling measurably improve with every project. This is where the volume advantage from above starts paying, and engineering owns accuracy tooling at scale.
