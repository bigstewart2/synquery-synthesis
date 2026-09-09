"""Canonical fictional Harbor demo inputs. Export browser assets with dev/sync_harbor.py."""

DEMO_ID = "harbor-v1"
BRIEF = {'project': 'Harbor payments diligence',
 'decision': 'We’re evaluating a payments platform serving mid-market distributors. Understand the '
             'drivers of growth, retention and margins, and the risks to investigate with management.',
 'questions': ['What drives customer acquisition, retention and switching?',
               'How do ERP integrations and partners affect growth and retention?',
               'What drives margins and recurring software revenue?',
               'What risks or assumptions need validation?',
               'What should we ask management or verify in company data?']}
SAMPLES = {'harbor-david': {'id': 'harbor-david',
                  'label': 'E1',
                  'name': 'David Okafor',
                  'role': 'Operations',
                  'filename': 'harbor-call-1-david-okafor-ops.txt',
                  'text': 'FICTIONAL DEMO INTERVIEW — Not a real person, company or investment '
                          'recommendation.\n'
                          '\n'
                          '# Expert Network Call Transcript\n'
                          '\n'
                          '**Project:** Diligence on a mid-market B2B payments platform (codename '
                          '"Harbor")\n'
                          '**Consultant:** Priya Raman, Senior Associate, Marlowe Consulting\n'
                          '**Expert:** David Okafor, former VP of Operations at a competing payments '
                          'processor (2018 to 2024)\n'
                          '**Date:** 2026-09-03\n'
                          '**Duration:** 45 minutes\n'
                          '\n'
                          '---\n'
                          '\n'
                          '**Priya:** Thanks for making time, David. Quick framing before we start. My '
                          'client is evaluating a payments platform that serves mid-market distributors '
                          "and wholesalers. I'm trying to understand what actually drives churn and "
                          "margin in this segment. I'll keep it to about forty minutes. Anything you "
                          "can't discuss, just say so.\n"
                          '\n'
                          '**David:** Understood. I can speak to how the segment works generally. I '
                          "won't get into anything specific to my former employer's numbers.\n"
                          '\n'
                          "**Priya:** That's fine. Let's start broad. When a mid-market distributor "
                          'picks a payments provider, what are they actually buying?\n'
                          '\n'
                          "**David:** Honestly, they think they're buying a processing rate. They're "
                          'actually buying reconciliation. A distributor doing forty million a year in '
                          'receivables has a two-person AR team drowning in remittance mismatches. The '
                          'provider that makes cash application take twenty minutes instead of four '
                          "hours wins, and it doesn't matter if their rate is ten basis points worse.\n"
                          '\n'
                          '**Priya:** So the rate is a tiebreaker, not the decision.\n'
                          '\n'
                          "**David:** The rate gets you into the conversation. The AR team's Friday "
                          'afternoon decides it.\n'
                          '\n'
                          "**Priya:** How would I test that? If I looked at a provider's churn data, "
                          "what would I expect to see if you're right?\n"
                          '\n'
                          '**David:** Churned accounts would cluster around ERP migrations. When a '
                          'distributor moves from, say, Sage to NetSuite, the integration breaks, the '
                          "reconciliation stops being automatic, and within two quarters they're "
                          "shopping. If churn is instead correlated with rate changes, I'm wrong.\n"
                          '\n'
                          "**Priya:** That's helpful. Let me push on it. Wouldn't an ERP migration be a "
                          'churn event for every provider, so it washes out competitively?\n'
                          '\n'
                          '**David:** No, because the good providers have pre-built connectors for the '
                          'top four or five ERPs. The migration is a churn risk only if your provider '
                          "doesn't have the connector ready on day one. So the question for your target "
                          'is how many native integrations they maintain and how fast they add new '
                          'ones. If the answer is "we use a middleware partner," that\'s a yellow '
                          'flag.\n'
                          '\n'
                          '**Priya:** Why yellow rather than red?\n'
                          '\n'
                          "**David:** Middleware works. It's just slower to fix when it breaks, and the "
                          "customer blames the payments provider, not the middleware vendor. It's a "
                          'service quality issue, not a structural one.\n'
                          '\n'
                          "**Priya:** Let's move to margin. Where does a provider in this segment "
                          'actually make money?\n'
                          '\n'
                          '**David:** Three places, in order. Interchange spread on card transactions, '
                          "though that's shrinking. Float on ACH, which most people underestimate. And "
                          'software fees, which is where everyone wants to be but few have earned.\n'
                          '\n'
                          '**Priya:** Say more on float.\n'
                          '\n'
                          "**David:** When a buyer pays by ACH, there's a window between when the money "
                          'leaves the buyer and when it settles to the seller. Depending on how the '
                          'provider structures settlement, they may hold that balance for one to three '
                          "days. At current rates, on a few billion in annual volume, that's real "
                          "money. It's also the first thing that disappears if rates fall, so I'd model "
                          'it separately.\n'
                          '\n'
                          '**Priya:** Would management call that out in their financials?\n'
                          '\n'
                          '**David:** Usually not cleanly. It often sits inside "other revenue" or gets '
                          "netted against processing costs. I'd ask for it explicitly. If they can't "
                          'isolate it, that tells you something about their finance function.\n'
                          '\n'
                          "**Priya:** What about the software fee piece. What separates the ones who've "
                          "earned it from the ones who haven't?\n"
                          '\n'
                          '**David:** Whether the customer would keep paying if processing went to '
                          'zero. If the answer is yes, because the invoicing, the portal, the '
                          "collections workflow are load-bearing, then it's software. If the software "
                          'is a thin wrapper that exists to justify a monthly fee, customers will '
                          'cancel it the moment a competitor bundles it free.\n'
                          '\n'
                          '**Priya:** How would I figure that out from the outside?\n'
                          '\n'
                          '**David:** Ask for logins per account per week. Not logins total. Per '
                          'account. A real software product gets used daily by the AR team. A wrapper '
                          'gets logged into once a month to download a statement.\n'
                          '\n'
                          "**Priya:** That's a good one. Let me ask about the competitive set. Who does "
                          'a provider like this actually lose deals to?\n'
                          '\n'
                          '**David:** It depends on size. Under ten million in revenue, they lose to '
                          "the bank's own offering, because the customer already has the relationship. "
                          'Over a hundred million, they lose to the big integrated players who can '
                          'bundle treasury services. The sweet spot is between those, and in that band '
                          'the main competitor is usually "do nothing," meaning the distributor keeps '
                          'paying by check and mailing lockbox.\n'
                          '\n'
                          '**Priya:** What share of that middle band is still on checks?\n'
                          '\n'
                          "**David:** I'd guess more than half, but that's a guess and you should "
                          "verify it. The point is that the market isn't primarily a share-shift game. "
                          "It's a conversion game. That affects how you should read a prowvider's "
                          'growth. Growth coming from check conversion is durable. Growth coming from '
                          "poaching another platform's accounts often reverses.\n"
                          '\n'
                          '**Priya:** How do I tell the two apart in a customer list?\n'
                          '\n'
                          '**David:** Ask for previous payment method at onboarding. Most providers '
                          "capture it in the sales CRM even if they don't report on it.\n"
                          '\n'
                          "**Priya:** Let's talk about risk. What's the failure mode for a company like "
                          'this that people miss?\n'
                          '\n'
                          '**David:** Concentration in a single vertical. Distribution looks '
                          'diversified from the outside because there are thousands of customers, but '
                          'if eighty percent of them are in building products, a housing slowdown hits '
                          "your whole book at once. I've seen a provider lose a fifth of volume in two "
                          "quarters because lumber pricing collapsed and their customers' buyers "
                          'stopped ordering.\n'
                          '\n'
                          '**Priya:** Anything on the fraud or compliance side?\n'
                          '\n'
                          "**David:** Less than you'd expect in B2B. The counterparties are known "
                          'businesses with invoices behind every payment. Where it bites is onboarding. '
                          "If the provider's KYB process is slow, sales cycles stretch, and that's a "
                          'growth problem more than a loss problem.\n'
                          '\n'
                          '**Priya:** Last area. If you were sitting in my seat and had one hour with '
                          "the target's management team, what would you ask?\n"
                          '\n'
                          '**David:** Three questions. One, what percentage of your volume runs through '
                          "native ERP connectors versus file uploads or middleware. Two, what's your "
                          'net revenue retention excluding accounts that churned during an ERP '
                          'migration, because I want to see the underlying number. Three, show me '
                          'weekly active users per account for the last eight quarters. If those three '
                          'come back clean, most of the other diligence is confirmatory.\n'
                          '\n'
                          "**Priya:** That's really clear. Anything you'd add that I didn't ask?\n"
                          '\n'
                          '**David:** One thing. Watch for how they treat their integration partners. '
                          'In this segment the ERP consultants who implement NetSuite and the like are '
                          'the real channel. If the provider has a partner program with real economics, '
                          "that's a moat. If they treat integrators as a cost center, expect the "
                          'integrators to steer customers elsewhere.\n'
                          '\n'
                          "**Priya:** Great. I'll write this up and may come back with a follow-up on "
                          'the float question if the client wants to model it. Thanks, David.\n'
                          '\n'
                          '**David:** Happy to help. Good luck with it.\n'},
 'harbor-maria': {'id': 'harbor-maria',
                  'label': 'E2',
                  'name': 'Maria Castellanos',
                  'role': 'Sales',
                  'filename': 'harbor-call-2-maria-castellanos-sales.txt',
                  'text': 'FICTIONAL DEMO INTERVIEW — Not a real person, company or investment '
                          'recommendation.\n'
                          '\n'
                          '# Expert Network Call Transcript\n'
                          '\n'
                          '**Project:** Diligence on a mid-market B2B payments platform (codename '
                          '"Harbor")\n'
                          '**Consultant:** Priya Raman, Senior Associate, Marlowe Consulting\n'
                          '**Expert:** Maria Castellanos, former SVP of Sales at a B2B payments '
                          'provider (2019 to 2025), now advising early-stage fintechs\n'
                          '**Date:** 2026-09-05\n'
                          '**Duration:** 40 minutes\n'
                          '\n'
                          '---\n'
                          '\n'
                          "**Priya:** Hi Maria, thanks for joining. So we're looking at a payments "
                          'platform for mid-market distributors and I wanted to get the sales '
                          'perspective. I spoke with an ops person earlier this week who said the whole '
                          "game is reconciliation, not rate. I'm assuming you'd agree with that?\n"
                          '\n'
                          "**Maria:** Partly. Reconciliation is what keeps the customer. It's not what "
                          'gets the meeting. Nobody takes a call because you promise better cash '
                          'application. They take the call because their bank just raised fees, or '
                          'their CFO read something about check fraud, or a competitor of theirs went '
                          "live on a portal and their buyers started asking why they can't pay online.\n"
                          '\n'
                          "**Priya:** Right, so there's a trigger event.\n"
                          '\n'
                          "**Maria:** Always. If I were looking at a provider's pipeline, the first "
                          "thing I'd want to know is what triggers they're built to catch. The ones who "
                          'grow are the ones with a repeatable trigger, not the ones with a better '
                          'product.\n'
                          '\n'
                          "**Priya:** Got it. So what's the sales cycle look like, roughly?\n"
                          '\n'
                          '**Maria:** For a distributor in the twenty to two hundred million range, '
                          'four to nine months from first call to first transaction. The variance is '
                          'almost entirely on the customer side. The CFO wants it, but AR has to '
                          "implement it, and IT has to approve the ERP connection, and IT's queue is "
                          'six months long.\n'
                          '\n'
                          "**Priya:** That's long. Is there anything a provider can do about that, or "
                          'is it just the segment?\n'
                          '\n'
                          '**Maria:** Two things. First, bring the ERP integrator in early. If the '
                          "customer's NetSuite consultant is on the second call, the IT objection "
                          'mostly disappears because IT trusts the consultant. Second, sell to the AR '
                          'manager, not the CFO. The CFO signs, but the AR manager decides whether the '
                          'project ever actually starts.\n'
                          '\n'
                          "**Priya:** That's interesting. The ops expert mentioned integrators as a "
                          'channel too. Can you say more on how a provider actually works with them? '
                          'Like what does the economic arrangement look like?\n'
                          '\n'
                          '**Maria:** Referral fees, usually a percentage of first-year revenue, '
                          "sometimes a small trailing piece. But money isn't really the lever. The "
                          'integrator cares about two things: does the integration make their '
                          'implementation harder or easier, and will the provider make them look bad. A '
                          "provider that's easy to implement and picks up the phone when something "
                          'breaks gets referrals without paying much. A provider that pays twenty '
                          'percent and breaks things gets nothing.\n'
                          '\n'
                          '**Priya:** Okay. So on pricing, how do these deals usually get structured?\n'
                          '\n'
                          '**Maria:** Basis points on card, flat fee per ACH, and a monthly platform '
                          'fee. The platform fee is where the negotiation happens. Sales reps will '
                          "waive it to close, and that's the number one way these companies end up with "
                          'a big customer base and no software revenue.\n'
                          '\n'
                          "**Priya:** So you'd expect the platform fee to be discounted a lot.\n"
                          '\n'
                          "**Maria:** I'd expect to see a lot of accounts paying zero platform fee and "
                          "then check whether anyone's ever gone back to reprice them. Most haven't. "
                          "It's a real opportunity if the product is good enough, and a real problem if "
                          "it isn't.\n"
                          '\n'
                          '**Priya:** How would I tell which?\n'
                          '\n'
                          '**Maria:** Find an account that had the fee reintroduced and see if they '
                          'stayed.\n'
                          '\n'
                          '**Priya:** Makes sense. Let me ask about competition. Who did you lose to '
                          'most often?\n'
                          '\n'
                          '**Maria:** The bank. Not because the bank was better. Because the bank was '
                          "already there and the CFO didn't want to have another conversation. The "
                          'second most common loss was to no decision. The deal just went quiet.\n'
                          '\n'
                          '**Priya:** What about the other fintech providers?\n'
                          '\n'
                          "**Maria:** Less than you'd think. In this segment the fintechs mostly aren't "
                          "competing with each other yet. They're all competing with the bank and with "
                          "inertia. That'll change, but it's not the current picture.\n"
                          '\n'
                          "**Priya:** So a provider's win rate against other fintechs wouldn't tell me "
                          'much.\n'
                          '\n'
                          "**Maria:** It would tell you about a small slice of deals. The number I'd "
                          "want is win rate against the incumbent bank. That's the real competition.\n"
                          '\n'
                          '**Priya:** What kind of win rate would be good there?\n'
                          '\n'
                          '**Maria:** Depends on how you count, and everyone counts differently. '
                          "Honestly I'd be skeptical of any number a management team gives me on this "
                          'without seeing the underlying opportunity list.\n'
                          '\n'
                          '**Priya:** Fair. So switching to retention. From a sales side, what does a '
                          'healthy book look like?\n'
                          '\n'
                          '**Maria:** Expansion. Distributors have multiple divisions and entities. A '
                          "good provider lands one division and rolls to the others. If a provider's "
                          "average account is one entity after three years, they're not selling into "
                          "the account after the close, and that's usually a sign the customer success "
                          'function is thin or nonexistent.\n'
                          '\n'
                          '**Priya:** And how would that show up in the numbers?\n'
                          '\n'
                          '**Maria:** Net revenue retention above a hundred and ten is the sign of a '
                          "book that's expanding. Below a hundred means they're leaking. The "
                          "interesting range is the middle, because that's usually a mix of some "
                          "accounts expanding a lot and others quietly shrinking, and you'd want to see "
                          'the distribution, not the average.\n'
                          '\n'
                          '**Priya:** Okay. Let me ask about the sales team itself. What should I look '
                          'for?\n'
                          '\n'
                          '**Maria:** Tenure and territory. If the average rep has been there under '
                          'eighteen months, the company is churning reps, which means the pipeline is '
                          'constantly being rebuilt from scratch and the forecast is fiction. And if '
                          "territories are by geography rather than by vertical, the reps don't build "
                          'the industry knowledge that makes the trigger-event selling work.\n'
                          '\n'
                          "**Priya:** That's useful. What about comp structure, is there anything "
                          'there?\n'
                          '\n'
                          "**Maria:** Whether reps are paid on volume or on revenue. If it's volume, "
                          "they'll sign anyone, including accounts that are unprofitable. If it's "
                          "revenue with a clawback on early churn, they'll be more selective.\n"
                          '\n'
                          '**Priya:** Last thing. If you had an hour with management, what would you '
                          'ask?\n'
                          '\n'
                          "**Maria:** What's the trigger event for your last twenty closed deals. Show "
                          "me platform fee by account, and which accounts pay zero. And what's your win "
                          "rate against the customer's existing bank, with the opportunity list to back "
                          'it up.\n'
                          '\n'
                          '**Priya:** Great. Anything else I should have asked?\n'
                          '\n'
                          '**Maria:** One thing. Ask about the buyer side. Every payment has two ends. '
                          "If the provider's buyer portal is bad, the distributor's customers complain, "
                          'and the distributor blames the provider. Most diligence only looks at the '
                          'seller experience. The buyer experience is where the surprise problems come '
                          'from.\n'
                          '\n'
                          "**Priya:** That's a good point, I hadn't thought about that. Thanks Maria, "
                          'this was really helpful.\n'
                          '\n'
                          '**Maria:** Anytime.\n'}}
