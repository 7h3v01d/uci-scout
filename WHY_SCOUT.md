# Why I Built UCI Scout

*by Leon Priest*

---

## The Protocol Isn't Enough

Once UCI existed as a protocol — a spec, two SDKs, proven interop, governance, audit — a different problem became clear.

Knowing *what* to build and knowing *where to start* are two different things.

A developer looks at a protocol specification and thinks: yes, this makes sense, I want my project to support this. Then they look at their codebase — maybe fifty files, maybe five hundred — and the question becomes: *how do I even begin?* What do I expose? What should be a capability? What's the risk level of each action? How do I map twenty service methods and a dozen API routes into a governed UCI manifest without spending a week on it?

That gap — between "I want UCI" and "I have UCI running" — is where adoption goes to die.

Scout exists to close that gap.

---

## The Blank Page Problem

Every integration project has a blank page moment. The point where you know what you're building toward but have no idea what the first line looks like.

For UCI, that blank page is the manifest. The `UCIManifest.json` that describes your node's capabilities, actions, risk levels, execution modes, transport, and governance. It's not complicated once you understand it — but writing one from scratch for an existing codebase, without any tooling, means manually reading through every route, every function, every class method and deciding: is this a UCI action? What category? What risk level? What are the input and output schemas?

Most developers don't do that. They try for an hour, it feels like too much work, and they move on.

I needed a tool that would do that reading for me.

---

## Why Static Analysis

The obvious approach would be to run the project and inspect what it exposes at runtime. Easier to implement, richer data.

Also completely the wrong approach.

Running unknown code to analyse it is an execution risk. It assumes the project can run in isolation. It assumes dependencies are installed. It assumes there's no side effect to starting the thing up. For a tool meant to work on *any* Python project — legacy codebases, half-finished services, projects you're auditing rather than maintaining — none of those assumptions hold.

Static analysis reads the source. Nothing executes. Nothing imports. Nothing runs. You point Scout at a directory and it reads Python files the same way a careful developer would — looking at decorators, function signatures, class structures, naming conventions — and draws conclusions from what it sees.

That means Scout works on every Python project that exists, not just the ones that happen to be easy to run.

---

## What Scout Actually Does

It finds the doors.

HTTP routes. CLI commands. WebSocket handlers. Celery tasks. APScheduler jobs. Event hooks. gRPC handlers. Public functions. Service layer methods. Anything that represents a callable interface into the software — Scout finds it, categorises it, assesses its risk, and maps it to a UCI capability.

Then it generates a manifest scaffold. Not a finished manifest — a head start. Every action has inferred execution modes, risk levels, input schema stubs built from Python type hints, and source location tags so you can navigate straight to the code behind each capability.

The first time you run it against a project you know well, and see it reflected back as a structured set of UCI capabilities with risk levels that mostly match your own intuition — that's the moment. That's when the protocol stops being an abstraction and becomes something you can ship.

That moment was the design goal. Everything else in Scout is in service of producing it.

---

## Zero Touch on the Target

One constraint was non-negotiable from the start: Scout must never touch the target project.

No files written. No imports added. No decorators required. No SDK installed in the target. No changes of any kind.

This matters for a few reasons. First, it means Scout can run on codebases you don't own or maintain — you're auditing, not modifying. Second, it means there's no risk of Scout breaking something in a project it's analysing. Third, it keeps the relationship honest: Scout is an observer. The developer decides what to do with what it finds.

The target project has no idea Scout was there. That's exactly right.

---

## Scout Is the On-Ramp

UCI is the road. Scout is the on-ramp.

You don't need Scout to use UCI — you can write a manifest by hand, integrate the SDK directly, build from scratch. Some developers will do exactly that.

But for the majority of developers sitting in front of an existing Python project wondering how to make it agent-ready, Scout is the answer to the first question: *what would this even look like?*

Run Scout. See your score. See your entry points mapped to capabilities. Save the scaffold. Edit the TODOs. Wire up the SDK. Ship it.

That path from zero to UCI-integrated should take an afternoon, not a week. Scout is why it can.

---

## What Comes Next

Scout is Python-only in v0.1. TypeScript support is next, then Go. OpenAPI spec ingestion to enrich action schemas automatically. A `--ci` flag so teams can gate deployments on UCI compatibility scores. A diff mode to compare scans against existing manifests and catch regressions.

The longer-term goal is that Scout becomes the standard way any developer — regardless of language, framework, or project age — answers the question: *how do I make this thing work with AI agents?*

Point. Scan. Ship.

---

*Leon Priest — Brisbane, Australia*
*github.com/7h3v01d*
*UCI Scout v0.1 — Apache 2.0*
