# What Maps of Making is

*Start here. Six short sections, no jargon. If you only read one page about this project, read this one.*

---

## Places with tools

Across Europe and beyond there are thousands of places where anyone can walk in and use
serious tools — 3D printers, laser cutters, woodshops, sewing machines, electronics benches.
They go by different names: makerspace, fablab, hackerspace, open workshop, repair café.

## The lists go wrong

Plenty of websites list these places. Most of those lists are wrong.

When a space opens, someone adds it to a directory. Then the opening hours change, or it
moves, or it quietly closes — and fixing that means updating fifteen+ different websites.
Nobody does. So the directories slowly fill with places that aren't there any more, and you
arrive at a locked door.

## We do it backwards

Normally you fill in a form on someone else's website, and they own your entry.

Maps of Making works the other way round. You publish **one small file** about your space at
an address you control — your own website, or free hosting. Then you tell us that address,
once. If you'd rather not write the file yourself, our guide writes it with you by asking
plain questions.

After that, we come to you. We read your file, over and over, and the map shows what it says
right now. You never fill in a form again. Change your file, and the map changes.

**Your file is the only thing that ever speaks for you.**

## You can leave whenever you want

It's your file, so you can stop. Move it, or delete it. The map notices and lets you go.
There's no account to cancel and nobody to ask.

## So the map can be honest

Because we keep coming back, the map knows something a directory can't: whether anyone is
still there.

A space whose file changed recently shows up bright. One nobody has touched in months fades.
One that disappears is marked as gone. The map stops pretending everything is fine.

## You can just ask

You don't have to come to our website and click around. Bring the map into the chat app your
group already uses and ask it things — *"which spaces near Ghent are open right now?"*,
*"who has a laser cutter?"*

It works today in **Matrix** and **Discord**. Plenty of other platforms need no new code —
only someone willing to try one first. If yours isn't on the list yet, that's an offer.

We're also building a way for your file to carry your **events**, so people can find what's
happening near them, not just where the tools are.

---

## What's real today, and what isn't

*This section is for readers of the documentation. It's deliberately blunt — if you're going
to build on this, you should know where the edges are.*

| | Status |
|---|---|
| Publishing a file and appearing on the map | ✅ works |
| The map re-reading your file and ageing the pin | ✅ works |
| Asking the map from Matrix or Discord | ✅ works |
| Other chat platforms | ⚙️ no new code needed — needs a first adopter to test and document |
| Events (`ext_events`) | 📋 designed, not built |
| Shared vocabulary across networks | ⚙️ partly — the vocabulary exists and is queryable; not every space uses it yet |

Gaps here are invitations, not apologies. The code is on [GitHub](https://github.com/nicolasdb/mapsofmaking) — issues and contributions welcome.
There is no chance we close every gap on our own.

## Where to go next

| If you want to… | Go to |
|---|---|
| Put your space on the map, step by step | [Tutorial: publish your first space](tutorial/01-publish-your-first-space.md) |
| Do one specific thing | [How-to guides](how-to/) |
| Look up how something actually behaves | [Reference](reference/) |
| Understand why it's built this way | [Explanation](explanation/) |
