# Synquery Take-Home Writeup

## The goal

Today the client gets raw transcripts and has to mine them by hand. The goal here is that after Synquery runs a panel, the client opens one page that already answers their question, with every claim sourced, and pulls what they need straight into their deck. Three hour-long calls become slide-ready data instead of homework.

## The idea

- Your interviewer already asks typed questions. Rank your top five criteria. Rate these vendors 1 to 10. Give me a per-user price. That means every transcript is secretly a filled-out survey, and today the client is the one turning it back into data by hand.
- So this product doesn't summarize transcripts. It pulls the typed answers out with their quotes and does all the math in code.
- The client's real job is putting claims on slides and defending them in a partner meeting. So the product's job is telling them what they're allowed to claim. Every number links to the exact moment it was said.

## What the client gets

- A findings table they can filter. Their themes and ours, kept separate on purpose, so it's clear where we added something they didn't ask for.
- The ratings matrix and the other numbers laid out as tables, sorted by vendor, since the vendor is what's being evaluated.
- The full transcripts. Every quote and every score clicks through to the moment it was said.
- A coverage tab that says plainly what three interviews can and can't support.
- A Summary tab that takes five claims a client might put on a slide and gives each a verdict. Supported, supported with caveat, or not supported by this panel, with a footnote written to paste under the slide.

## Where AI does the work, and where it doesn't

- AI does the reading. It finds the atoms in a transcript, a rating, a price, a quote, and drafts the one-line takeaways.
- Everything else is code. Every average, every count, every verdict, the citation check, the redaction, the wrong-scale catch. A number a model computed is a number a client can't defend.
- We store the atoms, a quote plus a timestamp. Every aggregate gets computed at build time. That way interview four updates every view without touching interviews one through three.
- I scored the extraction against ground truth I verified by hand. 52 of 52 vendor ratings, 11 of 11 prices, 106 of 106 quotes verbatim, zero made-up atoms.

## The data has real problems, and the product has to survive them

One rating came back as "9 out of 10" on a question asked 1 to 7, so it gets quarantined instead of averaged in. One price was actually paid and two were just quotes received, so every price carries its basis and unlike ones never get averaged together. Each expert ranked their own criteria instead of a shared set, so only 2 of 8 are comparable across the panel, and that one can only be fixed at interview design, not after. None of this is a knock on the interviewer. It's the job description for the synthesis layer, and each fix is cheap.

## Roadmap, the next five in order

1. **Human sign-off before anything reaches a client.** The automated checks catch broken citations and wrong scales. They can't catch a judgment call, and one wrong claim in front of a PE partner ends the design partnership. Days of work, and every reviewer edit becomes training data for item 5.
2. **Derive the interview guide from the client's question at setup.** The client states their question, we propose the structure it implies and the guide that fills it. Same criteria for every expert, one stated scale. The 2-of-8 problem was born in the guide and can't be repaired afterward. Over time this becomes a library of question types, each with its own matrix, built from real projects rather than invented from one.
3. **Real ingestion.** Three hand-placed files becomes a pipeline where atoms have stable IDs, so re-running extraction produces a diff instead of breaking citations a client already pasted into a deck. This is the first month's engineering.
4. **Export into their actual deck.** Slide and spreadsheet objects with the footnotes attached. Today clients would retype our numbers, and retyping is where errors get in.
5. **A standing accuracy score.** One perfect panel of three is a demo, not a warranty. Reviewer corrections from item 1 become the test set that every extraction change has to pass.

## Where I'd want an engineer first

The atom store and re-extraction, multi-tenant isolation once a second client's data shows up, eval at volume, and the review-queue workflow. I'd prototype all of it myself. I wouldn't let any of it carry client load without an engineer in the room.

## What I left out on purpose

No free-text question box. Sitting on three interviews, it would be a confident wrong-answer machine. Five fixed claims keep every verdict honest, and the box can come when the corpus can support it. Also cut, auth, multi-project switching, ingestion UI, and anything a table does better than a chart.
