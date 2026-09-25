\# Design Document (Proposal)

\## 1. Project Overview

\- \*\*Project Name: \* AdCup

\- \*\*Team Members: \*\*

\- 1. Wongsapat Kerdpol 6801596

\- 2. Teedej Sriprasert 68011544

\- 3. Puri Banluesrisak 68011497

\- 4. Sila Chailek 68011512

\- \*\*Objective:\*\* AdCup is a web platform that connects brand owners who want to promote their products with content creators (big and small) who want to earn money by making promotional videos. Brands post a campaign with a fixed reward budget and a published pay rate (a fixed rate per views, decided upfront and the same for every creator). Creators pick a campaign, make and post their own original promotional video (UGC), submit their post, and get paid once the brand approves the content and views come in — until the campaign's budget is fully used.

\- \*\*Scope:\*\*

\- \*\*Included:\*\* campaign creation, campaign browsing, open (no pre-approval) joining, content submission and view tracking, a brand approval step before any payout, first-come-first-served reward pool distribution logic (queue-based), simulated payment/checkout for funding a campaign, a real OAuth integration with YouTube to pull real view counts, a flat platform commission on every payout, an in-app wallet with withdrawal, and an admin analytics dashboard.

\- \*\*Excluded (for this course project):\*\* real payment/bank transfer of money(process takes longer than the course timeline)

\- \*\*Target User Persona:\*\*

\- \*\*Persona A — "Brand Owner":\*\* A small-to-medium business owner or marketing staff who wants an easy way to get user-generated content (UGC) for their product without hiring a big agency. Pain point: promoting a product is expensive and hard to measure results; they want a "pay only for results" system, and they want to keep control by approving what gets published under their name before paying for it.

\- \*\*Persona B — "Content Creator":\*\* A person who makes videos on TikTok/IG/YouTube, from beginners with no brand deals yet to established creators. Pain point: it is hard to find sponsors, especially for small creators; they want an easy way to find brand campaigns, and get paid fairly and transparently based on performance.

\## 2. Requirements

\### 2.1 Functional Requirements

\- Brand owner can register/login and create a campaign (product info, content rules, total reward budget, a fixed pay rate per views, allowed platforms, deadline).

\- Brand owner "funds" the campaign through a simulated checkout, which locks the reward budget to that campaign.

\- Content creator can register/login, browse open campaigns, and join any open campaign immediately.

\- Content creator can connect their YouTube account through Google OAuth to verify ownership; the app then pulls real view counts for videos they submit through the YouTube Data API.

\- Content creator can submit one or more videos per campaign (each submission is tracked separately).

\- System reviews each submission and approves or rejects it. A submission with no approval never generates a payout.

\- Once approved, the system calculates the payout for that submission from the campaign's remaining reward pool, in the order submissions were approved (first-come-first-served), until the pool runs out. Later approved submissions after the pool is empty earn nothing, and the app clearly shows the remaining pool balance so creators can decide if it's still worth joining.

\- Approved payouts are credited (minus platform commission) to the creator's in-app wallet balance; creators can withdraw once their balance passes a minimum threshold.

\- Brand owner can view campaign status (spend so far, number of creators joined, submissions pending approval, views generated).

\- Admin can view a business analytics dashboard (active users, transaction volume, projected revenue, campaign performance).

\- Toast notifications for success/error on key actions (e.g., campaign created, submission approved, payout processed).

\### 2.2 Non-functional Requirements

\- Passwords must be hashed (never stored as plain text); OAuth tokens stored securely and never exposed in the frontend.

\- Authentication handled with JWT for the app's own sessions, and Google OAuth 2.0 for YouTube account linking.

\- Fully responsive layout for desktop.

\- Form validation on both frontend and backend.

\- Simple, clear navigation so non-technical brand owners and creators can use the app easily.

\## 6. Monetization & Feature Gating

\*Note: the numbers below are based on published rates and reviews from real clipping-marketplace platforms, not made-up round numbers. Real campaigns pay roughly \$300–\$2,000 per 1,000,000 views depending on campaign type, and real clipping-marketplace platform publicly discloses a 10% commission on creator payouts, so we used those as our baseline (converted to THB at roughly 35 THB/USD).\*

\- \*\*Business Model:\*\* The platform's only revenue source is a \*\*flat commission fee taken from every payout to content creators\*\*. When a creator's approved submission earns money from a campaign's reward budget, the platform keeps a fixed percentage before the rest is credited to the creator's wallet. There is no subscription plan — every user has the same features and limits, and the only thing enforced by tier logic is the commission calculation itself.

\- \*\*Pay rate example:\*\* a campaign might publish a rate of \*\*25 THB per 1,000 views\*\* (≈ 25,000 THB per million views). A creator whose approved video hits 40,000 views earns 1,000 THB gross.

\- \*\*Commission example:\*\* the platform takes a flat \*\*10% commission\*\* so that 1,000 THB gross payout becomes \*\*900 THB net\*\* to the creator, with \*\*100 THB\*\* kept by the platform.

\- \*\*Feature Gating:\*\* This project does not use paid tiers or feature gating. All brand owners and creators have the same access, and the same analytics. The only thing that depends on money moving through the system is the automatic commission deduction on every payout, which still needs to be enforced in code (not a paid-tier restriction, but the platform's core monetization logic).

\- \*\*Payment / Checkout Flow (Simulated):\*\* There are two simulated/real flows in the app:

1\. \*\*Brand funds a campaign:\*\* When a brand creates a campaign, they go through a mock checkout (Stripe Test Mode or a fake QR code) to "deposit" the reward budget into the campaign's pool. No real money moves — the backend just records a successful transaction and locks that amount to the campaign.

2\. \*\*Creator submits and gets approved:\*\* The creator connects their YouTube account (real OAuth). Once the brand approves the submission, the backend calculates the gross payout from the campaign's remaining pool (first-come-first-served order), deducts the flat 10% commission, and credits the \*\*net amount\*\* to the creator's in-app wallet. Gross amount, commission amount, and net amount are all recorded.

3\. \*\*Wallet withdrawal:\*\* Once a creator's wallet balance passes a minimum threshold — we used \*\*1,500 THB (≈ \$43)\*\*, close to the \$50 minimum real creators report — they can request a withdrawal through a mock "Cash Out" flow. No real bank transfer happens, but the balance and a transaction record update as if it did.

\- \*\*Enforcement:\*\*

\- Each submission has a \`status\` field (pending / approved / rejected); only \`approved\` submissions are eligible for a payout calculation.

\- Each payout is stored as a row in the Transactions table with \`gross_amount\`, \`commission_amount\` (always 10%), and \`net_amount\`, processed in the order submissions were approved so the reward pool depletes fairly (first-come-first-served).

\- A FastAPI service function calculates the commission on every payout before crediting the creator's wallet, so the platform's revenue logic is enforced in code, not just described in the UI.

\## 10. Timeline and Milestones

\- \*\*Week 1 (by 23 Sep):\*\* Finalize idea, write and submit proposal, confirm team roles.

\- \*\*Week 2 (by 30 Sep):\*\* Set up the boilerplate repo, register the Google Cloud OAuth app for YouTube (testing mode), Build database schema (Users, Campaigns, Submissions, Transactions) and authentication (register/login + Google OAuth account linking). Target ~40% of the app.

\- \*\*Week 3 (by 7 Oct):\*\* Build campaign creation & browsing, submission flow (YouTube real view pull), brand approval screen, first-come-first-served payout calculation logic with commission deduction. Target ~70% of the app.

\- \*\*Week 4 (by 14 Oct):\*\* Finish wallet & withdrawal, admin analytics dashboard, full testing, record progress video.

\- \*\*Week 5 (by 21 Oct):\*\* Finish the complete Design Document, polish UI, record final demo video, prepare for onsite presentation.

\*\*Milestones:\*\*

\- Database schema completed.

\- Authentication & role-based access (Brand / Creator / Admin) working, including real YouTube OAuth linking.

\- Full flow working end-to-end: create & fund campaign → creator joins & submits → brand approves → payout calculated in submission order → creator withdraws.

\- Admin dashboard showing at least 3 key business metrics.
