"""Real Notion entities captured from actual sync for testing."""

from datetime import datetime

from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.notion import (
    NotionDatabaseEntity,
    NotionFileEntity,
    NotionPageEntity,
    NotionPropertyEntity,
)

# Database entity (captured from real sync - Sprint Board with comprehensive schema)
database = NotionDatabaseEntity(
    entity_id="1c120d45-f5f8-80b1-b236-f1aeeffb0119",
    breadcrumbs=[],
    name="Sprint Board",
    created_at=datetime(2025, 3, 25, 19, 1, 0),
    updated_at=datetime(2025, 10, 15, 12, 0, 0),
    title="Sprint Board",
    description="Stay organized with tasks, your way.",
    properties={
        "Due date": {"type": "date", "name": "Due date"},
        "Connector Wishlist": {"type": "checkbox", "name": "Connector Wishlist"},
        "Epic": {
            "type": "select",
            "name": "Epic",
            "options": [
                "Airweave Cloud",
                "Platform is stable",
                "Great Search",
                "Self-serve",
                "Compliant for Enterprise",
                "Killer Ops",
                "Awesome developer experience",
                "Platform is near realtime",
                "Kickstart PLG",
                "Tech Debt & Minor Bugs",
                "Product is ready for mass adoption",
                "UI is intuitive",
                "50 Connectors",
                "Technology is SOTA",
                "Monke",
                "New Entity System",
            ],
        },
        "Difficulty": {"type": "number", "name": "Difficulty", "format": "number"},
        "Task type": {
            "type": "multi_select",
            "name": "Task type",
            "options": [
                "Management",
                "🐞 Bug",
                "💬 Feature request",
                "💅 Polish",
                "Product",
                "Infra",
                "Recurring",
                "Admin",
                "⏳ Spike",
            ],
        },
        "Status": {
            "type": "status",
            "name": "Status",
            "options": ["Not started", "This week", "In progress", "Done"],
        },
        "Priority": {
            "type": "select",
            "name": "Priority",
            "options": ["High", "Medium", "Low"],
        },
        "Assignee": {"type": "people", "name": "Assignee"},
        "Customer": {
            "type": "multi_select",
            "name": "Customer",
            "options": [
                "Zeno",
                "Delty AI",
                "Luthor AI",
                "Bond",
                "Capacitive",
                "Picnic Health",
                "Den",
                "Kestral",
                "Cleon",
                "Vesence",
                "Dash",
                "BlueJay",
                "OpenMinder (Gideon)",
                "Dashdoc",
                "TaskCrew",
                "Optonal",
                "MineCompare",
                "Micro",
                "Wordware",
                "Pilot",
            ],
        },
        "Launch week": {"type": "checkbox", "name": "Launch week"},
        "Task name": {"type": "title", "name": "Task name"},
    },
    properties_text=(
        "Due date (date) | Connector Wishlist (checkbox) | Epic (select) options: "
        "Airweave Cloud, Platform is stable, Great Search, Self-serve, Compliant for "
        "Enterprise +11 more | Difficulty (number) format: number | Task type "
        "(multi_select) options: Management, 🐞 Bug, 💬 Feature request, 💅 Polish, "
        "Product +4 more | Status (status) options: Not started, This week, In progress, "
        "Done | Priority (select) options: High, Medium, Low | Assignee (people) | "
        "Customer (multi_select) options: Zeno, Delty AI, Luthor AI, Bond, Capacitive "
        "+15 more | Launch week (checkbox) | Task name (title)"
    ),
    parent_id="",
    parent_type="workspace",
    icon={
        "type": "external",
        "external": {"url": "https://www.notion.so/icons/checkmark_green.svg"},
    },
    cover=None,
    archived=False,
    is_inline=False,
    url="https://www.notion.so/1c120d45f5f880b1b236f1aeeffb0119",
)

# Page entity - THE DENSEST: Brand & Website Design (25,995 chars, 524 blocks, max depth 4)
page = NotionPageEntity(
    entity_id="25220d45-f5f8-8025-b372-c6375aa06824",
    breadcrumbs=[],
    name="Brand & Website Design",
    created_at=datetime(2025, 8, 17, 13, 26, 0),
    updated_at=datetime(2025, 10, 14, 16, 31, 0),
    parent_id="",
    parent_type="workspace",
    title="Brand & Website Design",
    content="""Document for upcoming design sprint with tonik.

**Date:**

*18–23 August 2025*

**Location:**

*Airweave HQ, Amsterdam*

**Airweave Team**

**[Table]**

**Tonik Team**

**[Table]**

[Image: image.png]

This document serves as a reference doc for Tonik during the design sprint.

The general idea is to capture Airweave's brand story, product positioning, target audience, goals for the website, and practical requirements (analytics, tracking, user journey). Aim is get into the design sprint with a clear shared vision and concrete inputs that Tonik can build from.

---

# ▸ Product & Brand

[Image: image.png]

**Core story and vision**

Airweave is a developer tool that gives AI agents the ability to retrieve timely, relevant, accurate, and actionable information from human-facing applications and databases. We provide the connective tissue that turns scattered private data into accessible agent knowledge.

Airweave **does not** build agents, **does not** do web search, and **is not** an API integration framework (like Composio, Klavis, or Pipedream).

**Mission and positioning**

We solve the problem of agent builders needing advanced, reliable search across many applications. Instead of spending weeks building fragile integrations, developers can add powerful search capabilities to their agents in just a few lines of code.

**Values and personality traits**

Serious, reliable, trustworthy, transparent, stable, developer-first, truth-seeking, quietly confident.

**Differentiation**

  - API designed specifically for use by agents, not humans

  - Focus on search across human-facing applications and databases

  - Simple developer experience, only a few lines of code required

**Tagline candidates (OLD!)**

  - *Build smarter agents*

  - *Empower agents with deep knowledge of your apps and workspaces*

**ELI5 explanation (for design metaphors/visuals)**

Airweave is like giving your AI agent a search bar into all your apps and databases, so it can instantly find the right information without the agent builder having to manually wire everything together.

---

# ▸ Audience & Use Case of Website

**Primary users**

  - Independent developers and hands-on engineers ("I just want to get my agent working")

  - Engineering managers or CTOs evaluating tooling

  - Startup founders building AI-native products

**Secondary audiences**

  - Investors (credibility and traction signals)

  - Potential hires (attracted by brand and vision)

  - Open source users (future contributors and community members)

**Customer journey for primary users**

A developer building agents encounters the '*search problem'* and lands on Airweave's site.

Roughly, this is the journey we want them to take:

  1. **Recognition of value**

    - Instantly see that Airweave solves their problem (agents need reliable access to app and database knowledge).

    - Trust that adoption requires minimal effort.

  1. **Exploration**

    - Learn how to implement Airweave with simple examples and clear explanations.

    - Quickly find pricing, packages, and technical documentation.

  1. **Action**

    - Create an Airweave account, or

    - Clone the repo and start building, or

    - Book a meeting with the team.

  1. **Conversion and retention**

    - Move from trial or open source use into a paid account.

    - Become part of the community (contributing, sharing, or scaling use).

**Tone for this audience**

Direct, developer-first, minimal friction e.g. "just ship the agent."

---

# ▸ Goals of Website

**Primary goals**

  - Convert individual developers, startup founders, and scale-ups into active users (signups, paid accounts).

  - Generate enterprise leads through demo requests or meetings.

**Secondary goals**

  - Drive account signups at **app.airweave.ai**.

  - Increase GitHub stars and repo engagement.

  - Grow our open source community.

**Tertiary goals**

  - Establish credibility and brand trust.

  - Support potential future hiring by making Airweave attractive to talent.

  - Signal momentum to (prospective) investors and partners.

  - Position Airweave as a thought leader in the AI infra space.

**Key calls to action (CTAs)**

  - **Sign up and start using now** (fastest path to value).

  - **Book a call / talk to us** (enterprise lead gen).

  - **Clone the repo** (open source adoption).

  - **Explore docs** (supporting developer self-serve).

**Content depth**

The site should balance **clarity and credibility**:

  - A minimal, fast landing page that convinces developers quickly.

  - Clear pathways into **docs, repo, and checkout.**

  - Enough detail to support enterprise and investor audiences without overwhelming first-time visitors.

**Must-haves from Airweave perspective**

  1. CTA for booking a call.

  1. Checkout flow for self-serve adoption.

  1. Prominent link to OSS GitHub repo.

  1. Clear path into documentation.

---

# ▸ Brand Style & Design Direction

[Image: image.png]

[Image: image.png]

[https://trytako.com/](https://trytako.com/)

[qdrant](qdrant.tech)

[firecrawl.dev](https://www.firecrawl.dev/)

[golf.dev](https://golf.dev/)

[Anthropic](https://www.anthropic.com/)

[langchain](https://www.langchain.com/)

[greptile](https://www.greptile.com/)

[https://mastra.ai/](https://mastra.ai/)

[https://www.better-auth.com/](https://www.better-auth.com/)

**Notes:**

Some links shared by Tonik team for inspiration

[Bookmark](https://land-book.com/)

[Bookmark](https://www.seesaw.website/)

[Bookmark](https://www.footer.design/)

**Some examples and our opinions:**

  - [https://www.greptile.com/](https://www.greptile.com/) (nice)

  - [https://www.perplexity.ai/hub](https://www.perplexity.ai/hub) (kinda nice)

  - [https://openai.com/news/](https://openai.com/news/) (not nice, to boring apple)

  - [https://www.langchain.com/](https://www.langchain.com/) (nice)

**Topics to touch on:**

  - Mood and feel: futuristic, technical, minimal, playful, corporate

  - Colors and typography preferences

  - Visual references: competitor sites we admire or dislike, and why

  - Logo and iconography: fixed or open to iteration

**Questions to answer:**

  - What mood and feel should the site project?

    - professional, simple, trustworthy

  - Are there specific colors or typography we want to use?

    - not necessarily, no overdone serif styling

  - Which competitor or reference sites do we like or dislike, and why?

    - everyone to share async

  - Is our logo fixed, or do we want to explore variations?

    - Logo stays is, color and size can change

---

# ▸ Current Design Assets

[Image: image.png]

[Image: Asset_2_1.svg]

**Current assets**

  - Logo: fixed, but color can be adjusted.

  - No real established color palette beyond the logo.

  - Limited product visuals (no strong screenshots or champion visuals yet).

  - No existing tagline or consistent messaging hierarchy.

**Tone of voice **(to be refined by Airweave)

We want to sound:

  - Developer-first and straightforward.

  - Serious, reliable, and trustworthy.

  - Confident but not flashy.

  - Transparent and clear, avoiding unnecessary hype.

**Messaging hierarchy **(to be refined by Airweave)

  - **One-liner:** clear statement of what Airweave is and does.

  - **Elevator pitch:** 2–3 sentences with value proposition.

  - **Longer description:** explanation of how it works, why it matters, and what sets it apart.

**Use cases / success stories**

  - No polished case studies yet.

  - Possible to highlight example use cases in future from agent builders once available.

  - For now: focus on showing *how Airweave works* with simple and clear diagrams, code snippets, and example workflows.

**Notes for Tonik**

  - Tonik is expected to help shape the **visual direction** since current design assets are minimal.

  - Airweave is in favor of visually attractive snippets and elements like diagrams, UI snippets and code examples.

  - We can provide input on technical explanations and example use cases during the sprint.

---

# ▸ Technical and Structural Considerations

For reference, our current landing page can be found at [https://airweave.ai/](https://airweave.ai/).

**Topics to touch on:**

  - Site architecture: homepage, product, docs, blog, community, careers

  - Build: CMS or static stack

  - Integrations: GitHub, Discord, analytics, newsletter signup

  - SEO and discoverability goals

**Extract from tonik agreement**

The new Airweave landing page s be designed to elevate the brand's visual identity, clearly present the product, and build trust with potential customers. The overall look and feel will be modern, clean, and tech-forward, aligning with the expectations of a developer and technical audience.

Key elements of the landing page:

  1. Hero section introducing the product with a strong visual identity and value proposition.

  1. Clear product explanations supported by structured content and visual hierarchy, ensuring technical users can quickly grasp what Airweave does and how it works.

  1. Code examples to demonstrate real use cases and help developers evaluate the implementation quickly.

  1. Pricing section with transparent tiers and benefits.

  1. Customer testimonials to build trust and validate the product's effectiveness.

  1. Blog section to support ongoing content marketing and SEO strategy.

  1. Motion and animations to add polish and improve user experience without overwhelming functionality.

The landing page will be built with scalability and maintainability in mind, enabling you to easily update content and extend functionality as the product evolves.

**Questions to answer:**

  - Which pages and sections must the site include?

    - Waar zijn we blij mee op huidige landing page?

    - Wat missen we op huidige landing page?

    - Wat willen we 100% niet op de landing page?

  - Do we have CMS/stack preferences?

  - Which integrations are essential? (in termen van analytics, widgets etc)

  - What SEO or discoverability outcomes do we want to achieve?

**Notes:**

Key elements of the landing page. resulting from 17/08 brainstorm.

  1. Hero section introducing the product with a strong visual identity and value proposition.

    1. tagline, subtitle, CTA, nice visual somehow,

  1. Code examples to demonstrate real use cases and help developers evaluate the implementation quickly.

    1. how to use (signal that its super easy to implement?)

    1. unblock people to get started ASAP

  1. Clear product explanations supported by structured content and visual hierarchy, ensuring technical users can quickly grasp what Airweave does and how it works.

  1. Customer testimonials / Social proof to build trust and validate the product's effectiveness.

  1. Pricing section with transparent tiers and benefits.

  1. Blog section to support ongoing content marketing and SEO strategy.

  1. Motion and animations to add polish and improve user experience without overwhelming functionality.

  1. FAQ?

📄 **[Landing Page [Copy] 1st Iteration]** (Child Page)

# Navigation

HOW AIRWEAVE WORKS  |  PRODUCT  |  PRICING  |  DOCS  |  GITHUB

---

# Hero

### Build agents that understand

*Hero alternatives:*

  - Give your agents the knowledge they need

  - Give your agents the context they seek

  - Give your agents the knowledge they need to work

  - Build agents that truly understand their users

  - Unlock your AI agent's true potential

*More hero alternatives:*

*Focus on agents:*

Agents that always find the answer

Build smarter agents (current)

Build agents you can trust

*Focus on search/retrieval:*

Let agents search any app (other current)

Retrieval you can rely on

Search that makes your agents smart

Search your agents can trust

Better search, better answers

*Knowledge/intelligence:*

Give your agents real knowledge

The knowledge layer for AI agents

# Hero Subtitle

Airweave turns your apps and databases into a single searchable source of truth, giving your agents accurate and grounded answers on demand.

*Hero subtitle alternatives:*

  - Airweave is an data retrieval layer for agentic applications.

  - Airweave is a context engineering platform that gives LLM agents powerful search across applications and databases. Turn scattered private data into actionable agent-knowledge.

  - Airweave is an information retrieval platform for AI agents.

# Hero CTA Buttons

[START FOR FREE] [BOOK A DEMO]

*Hero CTA button alternatives:*

  - [GET STARTED] [BOOK A DEMO]

  - [START BUILDING] [BOOK A CALL]

  - [START NOW] [BOOK A DEMO]

  - [GET STARTED] [REQUEST A DEMO]

  - [GET STARTED] [GET IN TOUCH]

---

# Social proof tagline

Trusted by engineering teams building the future

[Logo Slider]

*Social proof tagline alternatives:*

  - Trusted by engineering teams building the future of AI

---

[Dive into Airweave]

# How Airweave Works

*Alternatives:*

  - How does Airweave work?

  - How it works

[Animation]

**1. Connect your sources**

Airweave comes with ready-to-use search connectors for productivity tools, document stores, email, calendars, CRMs, and databases. No custom setup, no integration work.

**2. Create your source of truth**

Airweave continuously ingests structured and unstructured data from across your apps, synthesizes it into a powerful unified knowledge layer that is always in sync and always ready for your agents to query.

**3. Ask, answer, action.**

Agents query Airweave in natural language. Airweave retrieves the right context, re-ranks it, and delivers accurate actionable answers that supercharge your agent.

---

[Features]

From integration complexity to intelligent search in minutes

**Powerful Search**

Unblocks agents by letting them find the right answers across apps and formats. Airweave empowers agents with semantic, keyword, hybrid, time-aware, and agentic search with intent, context, and understanding of complex relationships and interdependencies.

**Real-time Data Sync**

Agents always see current information. No stale snapshots. No manual refreshing.

**Prebuilt Connectors**

Pick from a growing catalog of over 20 data sources. Configure once and let Airweave handle auth and sync.

**Framework friendly**

Drop Airweave into LangChain, Composio, Pipedream, or your custom agent stack. Five minutes from install to first answer.

**Open Source Philosophy**

Trust and transparency are our core tenants. Airweave is built in the open and improved by the community.

---

[Pricing]

# From passion project to scalable solution

*Some alternatives:*

The fastest way to production-ready search

All of the power, none of the complexity

Built for devs, ready for teams

From side project to enterprise scale

Start free, scale when you need to

Built for builders at every stage

For hackers and scalers

## Monthly - Yearly toggle

[MONTHLY / YEARLY [SAVE 20%]] toggle —>

  - **default setting is yearly**

  - prices should be reduced by 20% when annual

**Developer   Free**

Perfect for personal agents and side projects. No creditcard required.

Start building with:

  - 10 Source Connections

  - 50K Entities Synced / mo

  - 500 Queries / mo

  - Community Support

  - Button: [START FOR FREE] —> link to [https://app.airweave.ai/](https://app.airweave.ai/)

**Pro  $20**

Take your agent to the next level.

Plan includes:

  - 50 Source Connections

  - 100K Entities Synced / mo

  - 2K Queries / mo

  - 2 Team Members

  - Email Support

  - Button: [GET PRO] —> link to [https://app.airweave.ai/](https://app.airweave.ai/)

**Team  $299**

For fast-moving teams that need scale and control.

Plan includes:

  - 1000 Source Connections

  - 1M Entities Synced / mo

  - 10K Queries / mo

  - 10 Team Members

  - Dedicated Slack channel

  - Dedicated onboarding

  - Optional Add-On:

    - SOC-2

  - Button: [START FOR FREE] —> link to [https://app.airweave.ai/](https://app.airweave.ai/)

**Enterprise  Custom**

For all your organization's custom needs.

Plan includes:

  - Unlimited Source Connections

  - Dedicated support

  - Help with adoption and success

  - Optional Add-ons:

    - SLAs

    - Dedicated SOC-2

  - Button: [Book A Call] —> link to [https://airweave.typeform.com/to/Ys0JKkYZ](https://airweave.typeform.com/to/Ys0JKkYZ)

---

# Testimonial

[Can we hide this section until we have the testimonials from our customers? We're collecting them now]

---

# CTA Block

**Ready to build smarter agents?**

[START BUILDING FOR FREE] —> Link to [https://app.airweave.ai/](https://app.airweave.ai/)

[BOOK A CALL] —> Link to: [https://airweave.typeform.com/to/Ys0JKkYZ](https://airweave.typeform.com/to/Ys0JKkYZ)

---

# Our Blog

**Insights from the AI infrastructure frontlines**

**Blog 1: Building production ready agents: lessons learned**

How to ground answers in your private data with confidence.

**Blog 2: From data chaos to agent knowledge**

A guide to syncing sources and improving search quality over time.

---

# Frequently Asked Questions

**What is Airweave?**

Airweave is a data layer for AI agents. It connects to your apps and databases, syncs private data, and gives agents semantic, hybrid, and agentic search with context and intent.

**How is Airweave different from API integration tools**

Traditional tools connect one service to another. Airweave creates a searchable knowledge layer across many services and applications so agents can find the right information without the need for developers to maintain brittle point to point integrations.

**What applications can I connect**

Airweave supports dozens of applications out of the box, including CRMs, support platforms, document stores, cloud drives, BI tools, data warehouses, and more.

See the full list of supported sources *here.* Don't see what you need? Reach out and we'll help.

**How long does implementation take**

Most teams go from install to first answer in minutes.

**What agent frameworks do you support**

Use Airweave with Composio, Pipedream, or your custom framework. Call the SDK or API directly.

**How does Airweave handle privacy**

Your data stays under your control, always. You choose what to sync, who can access it, and you can remove it at any time. Airweave never shares your data outside your organization.

---

# Status and footer

All systems operational

DOCS  |  CONTACT US  |  BLOG  |  TERMS AND CONDITIONS  |  PRIVACY POLICY

© Airweave. All rights reserved.

📄 **[Landing Page [Copy] 2nd Iteration]** (Child Page)

# Navigation

HOW AIRWEAVE WORKS  |  PRODUCT  |  PRICING  |  DOCS  |  GITHUB

---

# Hero

final:

### Build smarter agents

*Hero alternatives:*

    - Give your agents the knowledge they need

    - Give your agents the context they seek

    - Give your agents the knowledge they need to work

    - Build agents that truly understand their users

    - Unlock your AI agent's true potential

    - Turn Scattered Data Into Agent Intelligence

*More hero alternatives:*

*Focus on agents:*

Agents that always find the answer

Build smarter agents (current)

Build agents you can trust

*Focus on search/retrieval:*

Let agents search any app (other current)

Retrieval you can rely on

Search that makes your agents smart

Search your agents can trust

Better search, better answers

*Knowledge/intelligence:*

Give your agents real knowledge

The knowledge layer for AI agents

Build Knowledgeable AI Agents

# Hero Subtitle

final:

Airweave turns your apps and databases into a single searchable source of truth, giving your agents accurate and grounded answers on demand.

*Hero subtitle alternatives:*

    - Airweave is an data retrieval layer for agentic applications.

    - Airweave is a context engineering platform that gives LLM agents powerful search across applications and databases. Turn scattered private data into actionable agent-knowledge.

    - Airweave is an information retrieval platform for AI agents.

# Hero CTA Buttons

final:

**[START FOR FREE] [BOOK A DEMO]**

  - [START FOR FREE] button links to: [https://app.airweave.ai/](https://app.airweave.ai/)

  - [BOOK A DEMO] button links to: [https://cal.com/lennert-airweave/airweave-demo](https://cal.com/lennert-airweave/airweave-demo)

*Hero CTA button alternatives:*

    - [GET STARTED] [BOOK A DEMO]

    - [START BUILDING] [BOOK A CALL]

    - [START NOW] [BOOK A DEMO]

    - [GET STARTED] [REQUEST A DEMO]

    - [GET STARTED] [GET IN TOUCH]

---

# Social proof tagline

Trusted by engineering teams building the future

[Logo Slider]

*Social proof tagline alternatives:*

  - Trusted by engineering teams building the future of AI

---

[Dive into Airweave]

final (please note the casing of the "Works"):

# How Airweave Works

*Alternatives:*

    - How does Airweave work?

    - How it works

[Animation]

final:

**1. Create Collection**

Spin up a searchable knowledge base.

**2. Add Sources**

Sync data from apps, docs, and databases with ready-to-use connectors.

**3. Supercharge Your Agent**

Your agent queries Airweave in natural language and gets accurate, grounded answers instantly.

---

[Features]

From integration complexity to intelligent search in minutes

**Powerful Search**

Unblocks agents by letting them find the right answers across apps and formats. Airweave empowers agents with semantic, keyword, hybrid, time-aware, and agentic search with intent, context, and understanding of complex relationships and interdependencies.

**Real-time Data Sync**

Agents always see current information. No stale snapshots. No manual refreshing.

**Prebuilt Connectors**

Pick from a growing catalog of over 20 data sources. Configure once and let Airweave handle auth and sync.

**Framework friendly**

Drop Airweave into LangChain, Composio, Pipedream, or your custom agent stack. Five minutes from install to first answer.

**Open Source Philosophy**

Trust and transparency are our core tenants. Airweave is built in the open and improved by the community.

---

[Pricing]

# From passion project to scalable solution

*Some alternatives:*

The fastest way to production-ready search

All of the power, none of the complexity

Built for devs, ready for teams

From side project to enterprise scale

Start free, scale when you need to

Built for builders at every stage

For hackers and scalers

## Monthly - Yearly toggle

[MONTHLY / YEARLY [SAVE 20%]] toggle —>

  - **default setting is yearly**

  - prices should be reduced by 20% when annual

**Developer   Free**

Perfect for personal agents and side projects. No creditcard required.

Start building with:

  - 10 sources

  - 500 queries / mo

  - 50K entities synced / mo

  - Community support

  - Button: [START FOR FREE] —> link to [https://app.airweave.ai/](https://app.airweave.ai/)

**Pro  $20**

Take your agent to the next level.

Plan includes:

  - 50 sources

  - 2K queries / mo

  - 100K entities synced / mo

  - 2 team members

  - Email support

  - Button: [GET PRO] —> link to [https://app.airweave.ai/](https://app.airweave.ai/)

**Team  $299**

For fast-moving teams that need scale and control.

Plan includes:

  - 1000 sources

  - 10K queries / mo

  - 1M entities synced / mo

  - 10 team members

  - Dedicated Slack support

  - Dedicated onboarding

  - Button: [GET TEAM] —> link to [https://app.airweave.ai/](https://app.airweave.ai/)

[NB: the bullet-points under "Optional:" should be indented]

**Enterprise  Custom**

For all your organization's custom needs.

Plan includes:

  - Unlimited source connections

  - Custom usage limits

  - Tailored onboarding

  - Dedicated priority support

  - Optional:

    - Custom integrations

    - On-prem deployment

    - SLAs

  - Button: [Book A Call] —> link to [https://cal.com/lennert-airweave/airweave-demo](https://cal.com/lennert-airweave/airweave-demo)

---

# Testimonial

[Can we hide this section until we have the testimonials from our customers? We're collecting them now]

---

# CTA Block

**Ready to build smarter agents?**

[START BUILDING] —> Link to [https://app.airweave.ai/](https://app.airweave.ai/)

[BOOK A CALL] —> Link to: [https://cal.com/lennert-airweave/airweave-demo](https://cal.com/lennert-airweave/airweave-demo)

---

# Our Blog

**Insights from the AI infrastructure frontlines**

**Blog 1: Building production ready agents: lessons learned**

How to ground answers in your private data with confidence.

**Blog 2: From data chaos to agent knowledge**

A guide to syncing sources and improving search quality over time.

---

# Frequently Asked Questions

**What is Airweave?**

Airweave is a data layer for AI agents. It connects to your apps and databases, syncs private data, and gives agents semantic, hybrid, and agentic search with context and intent.

**How is Airweave different from API integration tools**

Traditional tools connect one service to another. Airweave creates a searchable knowledge layer across many services and applications so agents can find the right information without the need for developers to maintain brittle point to point integrations.

**What applications can I connect**

Airweave supports dozens of applications out of the box, including CRMs, support platforms, document stores, cloud drives, BI tools, data warehouses, and more.

See the full list of supported sources *here.* Don't see what you need? Reach out and we'll help.

**How long does implementation take**

Most teams go from install to first answer in minutes.

**What agent frameworks do you support**

Use Airweave with Composio, Pipedream, or your custom framework. Call the SDK or API directly.

**How does Airweave handle privacy**

Your data stays under your control, always. You choose what to sync, who can access it, and you can remove it at any time. Airweave never shares your data outside your organization.

---

# Status and footer

All systems operational

DOCS  |  CONTACT US  |  BLOG  |  TERMS AND CONDITIONS  |  PRIVACY POLICY

© Airweave. All rights reserved.""",
    properties={},
    properties_text="",
    property_entities=[],
    files=[],
    icon={
        "type": "file",
        "file": {
            "url": "https://prod-files-secure.s3.us-west-2.amazonaws.com/95e03634-f1a9-4ab6-a1da-6b020aef92bc/360c9722-41c9-4b36-b700-0366a78bb80f/192721200.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=ASIAZI2LB4664DLMJ7RT%2F20251019%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20251019T100608Z&X-Amz-Expires=3600&X-Amz-Security-Token=IQoJb3JpZ2luX2VjECcaCXVzLXdlc3QtMiJGMEQCHxcISvxyg1auB%2ByiS3yLxCwQ6ZLViqGtAoqGXsPYGjQCIQDFY95au19FISXJ7y5K1OMDqQnKBb%2FvyhubZIJHcZGjhyqIBAjQ%2F%2F%2F%2F%2F%2F%2F%2F%2F%2F8BEAAaDDYzNzQyMzE4MzgwNSIM17zZzPVtDJAkNB%2FVKtwDD1jLGSLjAMT22tfTZZ3dp4frxxXyeb3YMZ6Qlb9bdeYD7eAJXarxv1a7B59jPPCdXslytcAkwzcjP%2Beqr8hKVENpFPggTAqE4ah7ri22haya%2BXOdNzRLLkWRlOKCRrJZ8u4AyjcsJQoGCc6nWK7%2F3%2BxuROvb6T9PbHsAFMkEwTd5%2B3g7AVixBCmXXEwJ8rNEC8rR%2FvgCKbqR4a2HmBUYSPyyAejykA5hsDmrRszLp4ZyujKgidSlRNEqsgKunB344xM80xBjx6BY6JTSv%2B%2B3vWe%2BqtjKdDtPLtMdGvFe2dQmpIJ3%2F%2Bk4tbow6kjeyf7Gf9O1oGbRkcqiFxlvY0eM8hly2FltarauCtzmDsHu6vjcBPJP%2Fz8d4r%2FIQ7wEYfYEdWGcjSNPMCdy%2BYaQkpjAu9USAElZ3XdcsRCscFeayi5Sd27Yyn2L5AQULILuRCKIupr4efYS2NQ%2FfhTNvgfzxWlSTDwRbE%2F%2Bmbowj5j4eNOns5y%2Br8xBYvyCM6bAAvbrUgZkVxkxaf%2F974qzbH7M%2FxtD%2BanhaYRvE61XHQP99r6OsTTZrX186bgf%2FcN9pdleLKWAq%2Bx56IExGNNaC4S9uulOrXJr9d1euktxwtl3SRIrblmCZgXUNrgM2fMw2ZzSxwY6pgHganwSmz8cGWYGHqSA4SRrv5FmI9YwUJ3r3BZAhns63CarIIWJdjC8tkl3hc9VfBWMgE9TnSDTOVLp04f%2BysHf8mn6HLgcyzDQSFgxksbDV5xXlsFQEUo350uxB7aVXJpGeLI6XtsPF6Vob75TQhwBu9FRJVYTYhQ2or0ly4WBb%2FEgUHvr0TP2LbPsoIBuhic5qKqS03sMwBooaGL6XWW5iBy4X2xY&X-Amz-Signature=c90fa4dd79e81f7f103dfffca5bbfa9e0aa3916efbc32103a479fd64853a5f0d&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject",
            "expiry_time": "2025-10-19T11:06:08.891Z",
        },
    },
    cover=None,
    archived=False,
    in_trash=False,
    url="https://www.notion.so/Brand-Website-Design-25220d45f5f88025b372c6375aa06824",
    content_blocks_count=524,
    max_depth=4,
)

# Property entity (from "Set up proper sync finalization CRUD" page - Epic property with value)
property_entity = NotionPropertyEntity(
    entity_id="1c220d45-f5f8-80f5-af6a-e72e693ef882_kyU~",
    breadcrumbs=[],
    name="Epic",
    created_at=None,
    updated_at=None,
    property_id="kyU~",
    property_name="Epic",
    property_type="select",
    page_id="1c220d45-f5f8-80f5-af6a-e72e693ef882",
    database_id="1c120d45-f5f8-80b1-b236-f1aeeffb0119",
    value={
        "id": "11909b38-b376-4a44-9c43-58ee09eaebe5",
        "name": "Airweave Cloud",
        "color": "red",
    },
    formatted_value="Airweave Cloud",
)

# File entity (captured from real sync with downloaded file)
file_entity = NotionFileEntity(
    entity_id="file_1e020d45-f5f8-805f-9181-cc96ec357be5_-6390150369527940729",
    breadcrumbs=[Breadcrumb(entity_id="1c120d45-f5f8-80b1-b236-f1aeeffb0119")],
    name="Screenshot_2025-04-24_at_18.09.15.png",
    created_at=None,
    updated_at=None,
    url="https://prod-files-secure.s3.us-west-2.amazonaws.com/95e03634-f1a9-4ab6-a1da-6b020aef92bc/cd53e2dc-f746-45fa-9a03-30f9d2f6d143/Screenshot_2025-04-24_at_18.09.15.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=ASIAZI2LB46642SAHZJP%2F20251019%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20251019T100353Z&X-Amz-Expires=3600&X-Amz-Security-Token=IQoJb3JpZ2luX2VjECcaCXVzLXdlc3QtMiJHMEUCIQC9aNu7puz9TYZt7blDU6CsOgH5fhyaajAF6fsiyL1UPAIgDYWmmyynJyElT%2FIgZJnuz9Lu%2FGcUao83AYPAdH3xYLoqiAQI0P%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARAAGgw2Mzc0MjMxODM4MDUiDHPPdja7uyJKY3JdRyrcA1izPF%2B22QvfqQWn3nusaMnX4qjrAoHRcvwiixv4X3WQ7Ai%2FxNoHrWuFr%2B%2FEAQIgW3syo8apd6gWvp94BvH6K8Z5DZ%2BddpSIxFNwfVis1DMsAsc786k6LtFtVnEAfuHLbfjI6dANGndtP3bnvtbqV72bc8qMc06wAwBkvdRy3KX26s7DNtL9MxhNhvNQYXSRzGCWMS5kKBlCVoC1d%2BGxYodBr94TTSYoj1MfBF%2FyZwWrC9Cmaq54APVakiLkRUrxWjnehmVKHp%2B5zHEgEtCDVLyS9tURDFm4qcnKZUj%2B2iYnhXIX40EcXW7c%2FetK7MT9UZXDb2lUXm5k0VmtzvxSeio1rV8fr5XZaeO0UHee2GHmtQvAuSKQd704Tchlac37Dn0kri9j9%2F2wcRQtw1H%2BUX8W48OV6i6q3KfpT2veQmX%2BrkunfMnioMrky10Go2oHmwcPupwG78Tb9RNfxDF%2BZaMhtmi2it5vwhhhD5wXDti5S6Y0dPzpl48wThsKiiS3VtcN9M088DP6%2FtrCEqwnm2hWR%2FuvWxvKh0wpwMkb3Rj20SM5NT1VeJAN%2FzdBqnznkZeutS4G5uY1REvUIlwNLUYn6PeRR68VVrW4LwpbDUlXRshRpnQvQoOGQBn5MKmX0scGOqUBVu04aBQO4Vh5t0MhK6vqsMGobCJjCwzzLYzLX0Y0c9hKdPQZKfmPmJdPi3ZdKb5SQmjAs0RxWsHFtyBym%2ByJxREVXJXxNNIoUI68TD%2BMqwhhG8WnDHjzwY%2FbWwUZrkE46Va4o4fYnrTiJlMdRNChI%2FjrHwbH5%2FJrDVzyJWOkdb%2BZAYXYC8KbkWZ7HSsjaXqh2fnlnbGrIoJSLrXDJ1KQEOJLEo4q&X-Amz-Signature=34e681d684a28a0f4f2af1271872c518736e017ecd0d53a4fcdb0a762efa693f&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject",
    size=0,
    file_type="image",
    mime_type="image/png",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Screenshot_2025-04-24_at_18.09.15.png"
    ),
    file_id="https://prod-files-secure.s3.us-west-2.amazonaws.com/95e03634-f1a9-4ab6-a1da-6b020aef92bc/cd53e2dc-f746-45fa-9a03-30f9d2f6d143/Screenshot_2025-04-24_at_18.09.15.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=ASIAZI2LB46642SAHZJP%2F20251019%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20251019T100353Z&X-Amz-Expires=3600&X-Amz-Security-Token=IQoJb3JpZ2luX2VjECcaCXVzLXdlc3QtMiJHMEUCIQC9aNu7puz9TYZt7blDU6CsOgH5fhyaajAF6fsiyL1UPAIgDYWmmyynJyElT%2FIgZJnuz9Lu%2FGcUao83AYPAdH3xYLoqiAQI0P%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARAAGgw2Mzc0MjMxODM4MDUiDHPPdja7uyJKY3JdRyrcA1izPF%2B22QvfqQWn3nusaMnX4qjrAoHRcvwiixv4X3WQ7Ai%2FxNoHrWuFr%2B%2FEAQIgW3syo8apd6gWvp94BvH6K8Z5DZ%2BddpSIxFNwfVis1DMsAsc786k6LtFtVnEAfuHLbfjI6dANGndtP3bnvtbqV72bc8qMc06wAwBkvdRy3KX26s7DNtL9MxhNhvNQYXSRzGCWMS5kKBlCVoC1d%2BGxYodBr94TTSYoj1MfBF%2FyZwWrC9Cmaq54APVakiLkRUrxWjnehmVKHp%2B5zHEgEtCDVLyS9tURDFm4qcnKZUj%2B2iYnhXIX40EcXW7c%2FetK7MT9UZXDb2lUXm5k0VmtzvxSeio1rV8fr5XZaeO0UHee2GHmtQvAuSKQd704Tchlac37Dn0kri9j9%2F2wcRQtw1H%2BUX8W48OV6i6q3KfpT2veQmX%2BrkunfMnioMrky10Go2oHmwcPupwG78Tb9RNfxDF%2BZaMhtmi2it5vwhhhD5wXDti5S6Y0dPzpl48wThsKiiS3VtcN9M088DP6%2FtrCEqwnm2hWR%2FuvWxvKh0wpwMkb3Rj20SM5NT1VeJAN%2FzdBqnznkZeutS4G5uY1REvUIlwNLUYn6PeRR68VVrW4LwpbDUlXRshRpnQvQoOGQBn5MKmX0scGOqUBVu04aBQO4Vh5t0MhK6vqsMGobCJjCwzzLYzLX0Y0c9hKdPQZKfmPmJdPi3ZdKb5SQmjAs0RxWsHFtyBym%2ByJxREVXJXxNNIoUI68TD%2BMqwhhG8WnDHjzwY%2FbWwUZrkE46Va4o4fYnrTiJlMdRNChI%2FjrHwbH5%2FJrDVzyJWOkdb%2BZAYXYC8KbkWZ7HSsjaXqh2fnlnbGrIoJSLrXDJ1KQEOJLEo4q&X-Amz-Signature=34e681d684a28a0f4f2af1271872c518736e017ecd0d53a4fcdb0a762efa693f&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject",
    expiry_time=datetime(2025, 10, 19, 11, 3, 53, 953000),
    caption="",
)

# All entities in one list
notion_examples = [database, page, property_entity, file_entity]
