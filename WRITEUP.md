# Synquery Take-Home Writeup

## The goal

Today the client gets raw transcripts and has to mine them by hand. The goal here is that after Synquery runs a panel, the client opens one page that already answers their question, with every claim sourced, and pulls what they need straight into their deck. Three hour-long calls become slide-ready data instead of homework.

## What I assumed

- The interview guide already comes from the client's question. That's how Synquery works today.
- The interviews keep asking typed questions, rankings, 1 to 10 ratings, prices. That's what makes the structure below possible.
- The client gives their question and a starting set of themes at kickoff.
- A human looks things over before anything goes out. This is a prototype for the Synquery team, not a finished client deliverable.

## What it does

- Structures everything the experts said. Ratings, prices, rankings, quotes, all pulled out as data with timestamps.
- Cites everything. Every number and every quote links straight to the moment it was said.
- Makes comparison easy. The same question across three interviews lands in one table instead of three documents.
- Takes a first crack at the key takeaways, which can guide the final deck.

## Who does what

| Step               | Today    | With this        |
|--------------------|----------|------------------|
| Run the interviews | Synquery | Synquery         |
| Pull themes        | Client   | Product          |
| Pull quotes, cite  | Client   | Product          |
| Build tables       | Client   | Product          |
| Compare interviews | Client   | Product          |
| Quality review     | Client   | Quick human pass |
| Build the deck     | Client   | Client, faster   |

The client goes from mining transcripts to reviewing findings and building their deck.

## What a client couldn't build themselves

The client brings their question and their starting themes. The product pulls its own themes on top, clearly marked as ours, so they see value beyond what they asked for. That second part compounds. Synquery analyzes interviews across many clients and projects, so the theme-pulling gets smarter with volume no single client ever has. A client could wire up their own transcript parser. They can't replicate that.

## Where AI does the work, and where it doesn't

- AI does the reading. It finds each data point in a transcript, a rating, a price, the quote behind a claim, and drafts the one-line takeaways.
- Everything else is code. Every average, every count, every verdict, the citation checks, the redaction. A number a model computed is a number a client can't defend.
- We store the extracted data points with their quotes and timestamps, and compute every table and aggregate from them. Interview four updates every view without touching interviews one through three.
- It flags data problems instead of papering over them. For example, a rating given as 9 out of 10 on a question asked 1 to 7 gets held out of the averages, not blended in.
- I checked the extraction against an answer key I verified by hand, and it matched. The scoring script is in the repo.

## Roadmap, the builds that make this a real product

1. **A review workspace.** Nothing reaches a client until a person has walked the takeaways and verdicts and signed off. The automated checks catch broken citations and wrong scales. They can't catch judgment. Small build, and every correction a reviewer makes feeds item 5.
2. **Client setup.** A real intake where the client enters their question and starting themes and the product proposes the output structure back. In the prototype that's hardcoded to this one project. This is what makes it work for any project.
3. **Ingestion.** Plug into the interview system so finished calls flow straight in, with stable IDs on every data point, so re-running extraction updates citations instead of breaking ones a client already pasted into a deck.
4. **Export.** One click into slides and spreadsheets with the footnotes attached, so nobody retypes numbers.
5. **Get smarter with volume.** Reviewer corrections become a running test set, and theme-pulling improves across projects. This is the piece that compounds, and the piece from the section above that a client can't replicate.

## Where I'd want an engineer first

- The data layer. When extraction re-runs with a better model, every citation a client already used has to survive. Retrofitting that later means breaking links in decks that already shipped.
- Client separation. Once a second client's data is in the system, keeping them walled off is a data-model decision, not a feature you bolt on.
- The review system at scale. Routing, who signed off on what, and versioning once a human is in the loop on every delivery.

I'd prototype all of it myself. I wouldn't let any of it carry client load without an engineer in the room.

## What I left out on purpose

No free-text question box. Sitting on three interviews, it would be a confident wrong-answer machine. Fixed claims keep every verdict honest, and the box can come when the corpus can support it. Also cut, auth, multi-project switching, ingestion UI, and anything a table does better than a chart.
