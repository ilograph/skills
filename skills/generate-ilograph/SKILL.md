---
name: generate-ilograph
description: Evaluate the current codebase and generate Ilograph sequence diagrams of it.
---

Analyze the codebase in the current working directory and produce `ilograph.yaml` — an [Ilograph](https://www.ilograph.com/) diagram capturing its architecture.

## Phase 1 — Explore the codebase

Before writing any YAML, invest time understanding the code:

- Identify the language(s), framework(s), and top-level package structure
- Find the main entry point and the central orchestrator class or module (the one that owns the main event loop or request lifecycle)
- Map the key modules/packages/classes by responsibility (e.g., extraction, networking, processing)
- If the solution's language(s) use(s) classes, identify class hierarchies: who inherits from whom, which base classes define shared behaviour
- Find all external actors: end-users, databases, message queues, third-party APIs, CDNs, external tools
- Identify important end-to-end flows — prefer flows that exercise different code paths (e.g., one happy path per major feature, one that shows error handling or an interesting architectural wrinkle). The number of flows can vary, but it is generally proportional to the size of the codebase. Tiny utility codebases may have a single flow, while large projects could have dozens.
- Once these are identified, present these flows, each with a brief description, to the user and ask them to choose which flows they would like diagrammed. Also offer to proceed using a collection of flows you judge as the most important so the user doesn't have to choose.

If the user asks for specific flow(s), use these instead.

Only proceed to writing YAML once you have a clear mental model of the above.

---

## Phase 2 — Write `ilograph.yaml`

The file has two top-level sections: `resources:` and `perspectives:`.

### YAML formatting rules (strictly enforced)

Use **compact block sequence** style throughout: list item dashes align with their parent key, not indented two extra spaces.

```yaml
# CORRECT
resources:
- name: MyPackage
  children:
  - name: MyModule
    children:
    - name: MyClass

# WRONG — do not use this style
resources:
  - name: MyPackage
    children:
      - name: MyModule
```

Nested **mappings** (non-list properties) are indented 2 spaces from their parent key as normal:

```yaml
- name: Foo
  description: |
    Multi-line text here.
  sequence:
    start: User
    steps:
    - to: Bar
      label: Do something
      description: |
        <more details here>
```

**Write each `description:`/`notes:` paragraph as one flowing line inside the block scalar — don't hard-wrap at a fixed column.**. Always use block scalar with a literal style (i.e. starting with `|` and a new line). YAML block scalars preserve embedded line breaks as literal breaks in Ilograph's rendered text, so a manually wrapped paragraph shows up with awkward mid-sentence breaks in the UI. Only start a new line for an intentional paragraph break.

```yaml
# WRONG — hard-wrapped, renders with a mid-sentence break
notes: |
  This flow validates the token and then queries the
  database before returning the result.

# CORRECT — single flowing line
notes: |
  This flow validates the token and then queries the database before returning the result.
```

---

### Prose style guidelines

When writing descriptions/notes, use plain English and a technical, formal writing style. Avoid editorializing and over-explaining; assume your audience is an experienced professional.

### Resources section

#### Abstract types

Create abstract types that act as reusable style definitions. Common ones include packages, modules, classes, and external services. Top-level "package" abstract types have a `dashed` style and a slightly tinted background color, by convention.

```yaml
resources:
- name: Package
  abstract: true
  style: dashed
  backgroundColor: "#fafafa" # slight tint (gray)

- name: Python Package
  abstract: true
  style: dashed
  icon: Dev/python.svg
  backgroundColor: "#f8faf8" # slight tint (green)

- name: Go Package
  abstract: true
  style: dashed
  icon: Dev/go.svg
  backgroundColor: "#faf8fa" # slight tint (purple)

- name: Python Module
  abstract: true
  color: "#306998"
  icon: Dev/python.svg

- name: Python Class
  abstract: true
  color: "#306998"
  icon: Dev/python.svg

- name: External Service
  abstract: true
  color: DimGray
```

If the repository uses multiple programming languages, create corresponding abstract types for each (e.g. create both `Python Class` and `Typescript Class`).

Be sure to not use `Class` types for programming languages that do not use classes, such as Rust and Go. For these, the preferred lowest-level type is "Module" (e.g. `Rust Module`).

Abstract resources do not appear as nodes in diagrams — they are templates only.

**Resource Colors**
When assigning resource colors, pick colors and styles that visually distinguish the categories. Prefer darker, more muted colors (e.g. `Firebrick` instead of `Red`). Here are some suggested resource colors:

Packages: no color specified, or `Dimgray`
External services: no color specified, or `Dimgray`

*By programming language*
- Typescript: `"#3178c6"`
- Rust: `"#B7410E"`
- C: `"#00599C"`
- C++: `"#004482"`
- C#: `"#178600"`
- Python: `"#306998"`
- Go: `"#009DB8"`
- React: `"#3d8ea4"`
- Javascript: `"#323330"`
- Dockerfile: `"#384d53"`
- Java: `"#b07219"`
- Ruby, CMake: `"#701516"`
- Batchfile, Makefile, Shell: `"#427819"`

Other colors to consider: `DarkSlateBlue`, `SteelBlue`, `CadetBlue`, `DarkCyan`, `Firebrick`, `DarkGreen`, `DarkRed`

#### Resource hierarchy

Model the codebase as a nested tree that mirrors the directory/package structure. Each node has:

- `name:` — short label (filename, class name, or package name). If this value contains restricted characters (/, ^, *, [, ], or commas), be sure to also give the resouce an `id` (see below).
- `instanceOf:` — one of your abstract types
- `description:` — 1–3 sentences: what this module/class is responsible for, its key public API surface, and any notable architectural role. Always use block scalar with a literal style (i.e. starting with `|` and a new line)
- `children:` — nested sub-modules or classes
- `id:` — required if `name` (see above) contains a restricted character (/, ^, *, [, ], or commas). In such cases, give resources an `id` property similar to its name but without the restricted character (for instance, substituting an underscore). When referencing these resources in perspectives, use this id instead of its name.
- `icon:` — an optional icon reference. Use only one of Ilograph's built-in icons (see next section), if any.

**Include only resources that appear in at least one perspective, or has a descendant resource that appears in at least one perspective.** Prune aggressively; a diagram with 60 nodes is less useful than one with 20.

When creating the resource hierarchy, create top-level resource(s) that organize modules/classes. For instance, if a repo includes both client-side and server-side packages, these top-level resources could be `Client` and `Server` packages. At the very least, include a top-level package for modules/classes to separate them from external resources (such as databases or external services). External resources generally don't themselves need to go under a top-level resource.

Packages with many resources can be further broken down. A common pattern is to segment packages into sub-packages by "layers" traditional to software architecture. For example, a Client package could be broken down further into a `UI` layer (for UI components and pages) and an `API Client` layer for server interactions. Meanwhile, the "Server" package could be broken down into a "Router" layer (for routers and handlers), a "Domain" layer (for domain-specific modules), and a "Data" layer for interacting with, for instance, databases. Give these sub-package resources, or the abstract types they inherit from, the `dashed` style.

Resources names in the tree do not necessarily have to be unique. If any two resources have the same name, give one (or both) unique `id`s, and use those ids when referencing them in perspectives.

#### Built-in icons for resources

##### Language-specific, for use in code-level modules and classes

Dev/apex.svg
Dev/apl.svg
Dev/awk.svg
Dev/ballerina.svg
Dev/bash.svg
Dev/c.svg
Dev/cairo.svg
Dev/carbon.svg
Dev/ceylon.svg
Dev/clarity.svg
Dev/clojure.svg
Dev/clojurescript.svg
Dev/cobol.svg
Dev/coffeescript.svg
Dev/cplusplus.svg
Dev/crystal.svg
Dev/csharp.svg
Dev/dart.svg
Dev/delphi.svg
Dev/dyalog.svg
Dev/elixir.svg
Dev/elm.svg
Dev/embeddedc.svg
Dev/erlang.svg
Dev/fortran.svg
Dev/fsharp.svg
Dev/gleam.svg
Dev/go.svg
Dev/groovy.svg
Dev/haskell.svg
Dev/haxe.svg
Dev/java.svg
Dev/javascript.svg
Dev/jule.svg
Dev/julia.svg
Dev/kotlin.svg
Dev/labview.svg
Dev/lua.svg
Dev/matlab.svg
Dev/nim.svg
Dev/objectivec.svg
Dev/ocaml.svg
Dev/perl.svg
Dev/php.svg
Dev/powershell.svg
Dev/processing.svg
Dev/prolog.svg
Dev/purescript.svg
Dev/python.svg
Dev/r.svg
Dev/racket.svg
Dev/reach.svg
Dev/rexx.svg
Dev/ruby.svg
Dev/rust.svg
Dev/scala.svg
Dev/solidity.svg
Dev/swift.svg
Dev/typescript.svg
Dev/vala.svg
Dev/visualbasic.svg
Dev/vyper.svg
Dev/wolfram.svg
Dev/zig.svg

##### Frameworks and libraries, use when confident a language-level construct is principaly using one of these libraries or frameworks

Dev/react.svg
Dev/angular.svg
Dev/vuejs.svg
Dev/svelte.svg
Dev/jquery.svg
Dev/nextjs.svg
Dev/nuxtjs.svg
Dev/gatsby.svg
Dev/redux.svg
Dev/bootstrap.svg
Dev/tailwindcss.svg
Dev/materialui.svg
Dev/d3js.svg
Dev/threejs.svg
Dev/electron.svg
Dev/express.svg
Dev/nestjs.svg
Dev/django.svg
Dev/flask.svg
Dev/fastapi.svg
Dev/rails.svg
Dev/laravel.svg
Dev/spring.svg
Dev/symfony.svg
Dev/dotnetcore.svg
Dev/flutter.svg
Dev/reactnative.svg
Dev/ionic.svg
Dev/xamarin.svg
Dev/tensorflow.svg
Dev/pytorch.svg
Dev/keras.svg
Dev/pandas.svg
Dev/numpy.svg
Dev/scikitlearn.svg
Dev/opencv.svg
Dev/jest.svg
Dev/vitest.svg
Dev/mocha.svg
Dev/selenium.svg
Dev/pytest.svg
Dev/cypressio.svg
Dev/playwright.svg
Dev/unity.svg
Dev/unrealengine.svg
Dev/godot.svg
Dev/mobx.svg
Dev/rxjs.svg
Dev/lodash.svg
Dev/prisma.svg

###### Databases, use when the solution calls for specific databases

Dev/aerospike.svg
Dev/cassandra.svg
Dev/clickhouse.svg
Dev/cosmosdb.svg
Dev/couchbase.svg
Dev/couchdb.svg
Dev/duckdb.svg
Dev/elasticsearch.svg
Dev/faunadb.svg
Dev/firebase.svg
Dev/firebird.svg
Dev/influxdb.svg
Dev/mariadb.svg
Dev/memcached.svg
Dev/microsoftsqlserver.svg
Dev/mongodb.svg
Dev/mysql.svg
Dev/neo4j.svg
Dev/postgresql.svg
Dev/realm.svg
Dev/redis.svg
Dev/rocksdb.svg
Dev/spicedb.svg
Dev/sqlite.svg
Dev/supabase.svg
Dev/surrealdb.svg
Dev/vitess.svg
Dev/yugabytedb.svg

##### Networking icons, used primarly for networking diagrams, but also can be used for generic databases, web servers, and other (mostly external) resources

Networking/antenna-tower.svg
Networking/browser-search.svg
Networking/cloud-hosting.svg
Networking/cloud-network-storage.svg
Networking/cloud-server.svg
Networking/computer-link.svg
Networking/computer-network.svg
Networking/data-structure.svg
Networking/data-synchronization.svg
Networking/database-files.svg
Networking/database-secure.svg
Networking/database.svg
Networking/datacenter.svg
Networking/desktop.svg
Networking/encryption.svg
Networking/error.svg
Networking/firewall.svg
Networking/folder-security.svg
Networking/hacker.svg
Networking/hard-drive.svg
Networking/internet.svg
Networking/laptop.svg
Networking/mobile-network.svg
Networking/mouse.svg
Networking/network-hub.svg
Networking/network-performance.svg
Networking/network-switch.svg
Networking/network-web.svg
Networking/router.svg
Networking/server-settings.svg
Networking/server.svg
Networking/speed-test.svg
Networking/trash.svg
Networking/user.svg
Networking/vpn.svg
Networking/web-server.svg
Networking/workstation.svg

##### AWS, Azure, GCP resources

These icons would be used when (and only when) diagramming a solution built to run on one of these cloud platforms. There are too many to list here, if cloud icons are needed see the full list of built-in Ilograph icons under ./references/iconlist.txt

#### Code references in prose

Wrap function/method names, enum and constant names, filenames, and struct/type names in backticks inside `description:` and `notes:` text — Ilograph renders them in monospace, which makes technical prose much easier to scan. **Never add backticks inside `label:` values** — labels don't support markdown and would show the backticks literally. When referencing files, don't include the full file path, since those can run long and cause formatting issues.

#### External actors
At the start of the `resources:` section, before the main codebase tree, add human actors as resources (`User`, and, if applicable, `Admin`, `Invitee`, etc.). If there are two or more human actors, group them under a `Users` resource like the following. If, conversly, there is only one human user, it can be a top-level resource.

```yaml

- name: Users
  style: dashed
  children:
  - name: User
    subtitle: End user
    icon: Networking/user.svg

  - name: Admin
    subtitle: System administrator
    icon: Networking/user.svg
```

#### External services

Also add resource per external system (databases, APIs, CDNs). Group related endpoints as children when appropriate:

```yaml
- name: GitHub API
  instanceOf: External Service
  children:
  - name: REST API
  - name: GraphQL API
```

### Perspectives section

Create **one relation perspective per important structural relationship** and **one sequence perspective per important flow**. Aim for 5–8 perspectives total, with sequence perspectives outnumbering relation perspectives.

---

#### Sequence perspectives

Each sequence perspective walks through one end-to-end flow. A basic structure:

```yaml
- name: <Flow name>
  notes: |
    1–3 sentence overview: what triggers this flow, what it does, and any
    architectural decisions worth highlighting (e.g., "Unlike X, this flow
    uses Y because Z"). Begin these notes with the words "This perspective", 
    e.g. "This perspective shows..." or "This perspective details..."
  sequence:
    start: User
    steps:
    - to: <entry-point resource>
      label: <action label>
      description: |
        What happens here.
    - subSequence:
        name: <Phase name>
        color: "<hex>"
        notes: |
          What this phase does and why it's worth calling out separately.
        steps:
        - to: <resource>
          label: <label>
          description: |
            <detail>
        - to: <resource>
          label: <label>
          description: |
            <detail>
        - to: <resource>
          label: <label>
          description: |
            <detail>
    - to: <entry-point resource> # Return back up call stack
      label: <Return type>
      description: |
        <Some details on the return value>
    - to: User # Return to user
      label: <Return type>
      color: gray # Repeated calls that return values up the call stack can be given the color `gray` and the descption can be omitted.
    
    - to: <anoter entry-point resource>
      label: <action label>

    # ...
```

**Step type reference:**

| Type | Use when |
|---|---|
| `to: X` | Control transfers to X and stays there |
| `toAndBack: X` | Synchronous call-and-return (request + response in one step). Control transfers back to the caller automatically. Avoid using this. |
| `toAsync: X` | Fire-and-forget / async notification. Control doesn't transfer; the caller does not wait on a response. |
| `restartAt: X` | Used to transfer control without displaying an arrow. Use sparingly in specific situations (see below) |
| `subSequence:` | Visual grouping of related steps into a named phase — does NOT affect control flow position |

**What to include**

In general, include steps (and subsequences of steps) that are "significant." Steps that cross domains (e.g. front-end to back-end, or back-end to database, or back-end to external service) are almost always significant. Things like error handing, retry logic, internal caching, and so on are not significant and can be ommitted. Internal steps, such as a class method calling another method on itself, are generally not significant. A web client fetching static web assets (html files, css files, etc.) are also generally not significant.

**Conventions for method dispatch (OOP codebases):**

When a concrete class calls an inherited method on a base class, make the dispatch visible:

```yaml
# Concrete → base dispatch (MRO / virtual dispatch)
- to: ConcreteClass
  label: Call method
  description: |
    YoutubeDL calls `foo()` on the ConcreteClass instance.
- to: BaseClass
  color: DimGray
  label: (Base dispatch)
  description: |
    ConcreteClass defines no `foo()` override; MRO resolves to BaseClass.
- to: BaseClass # Self-calling step for internal processing
  label: Execute base implementation
  description: |
    BaseClass.foo() does the actual work
- to: ConcreteClass
  color: gray
  label: Return result # Whatever the return value was
- to: CallerClass
  color: gray
  label: Return result # Whatever the return value was
```

Remember to use `color: gray` for return-path steps that have no interesting content — they just move the position indicator back up the call stack.

**Conventions for asynchronous calls, background workers, webhooks, polling, and similar**

Use `toAsync: X` for asynchronous/fire-and-forget/out-of-band calls where the caller does not wait for a response from the callee.

Tasks that are performed by background workers while their clients wait can be shown in the same sequence by using `restartAt:`.

```yaml
start: User
steps:
- to: Audit (Client)
  label: Start a site audit
  description: |
    <description>
- to: startAudit
  label: Call start-audit server function
  description: |
    <description>
- to: RequireProjectContext
  label: Authorize project access
  description: |
    <description>
- to: startAudit
  label: Project access authorized
  color: gray
- to: AuditService
  label: Start audit
  description: |
    <description>
- to: AuditRepository
  label: Create audit row (running)
  description: |
    <description>
- to: AuditService
  label: Audit row created
  color: gray
- toAsync: SiteAuditWorkflow
  label: Create workflow instance
  description: |
    <description>

- to: startAudit
  label: Audit ID
  description: |
    <description>
- to: Audit (Client)
  label: Audit ID
  description: |
    <description>
- to: User
  color: gray
  label: Notify user of running audit
  # No description required here, since this is a simple "return" step

- restartAt: SiteAuditWorkflow # Move control to `SiteAuditWorkflow`

- to: SiteAuditWorkflow # Self-referencing step
  label: Execute workflow phases
  description: |
    <description>

# Other steps here as SiteAuditWorkflow executes the task asynchrnously while the client waits
# ...
      
- restartAt: Audit (Client) # Move control to `Audit (Client)`
- to: getAuditStatus
  label: Poll for audit status
  description: |
    <description>
- to: AuditService
  label: Get audit status
  description: |
    <description>
- to: AuditRepository
  label: Get audit status
  description: |
    <description>
- to: AuditService
  label: Audit status
  color: gray
- to: getAuditStatus
  label: Audit status
  color: gray
- to: Audit (Client)
  label: Audit status
  color: gray
  
# ...
```

**SubSequence phase colours** (suggested progression within a perspective):

- `"#1525c0"`
- `"#e62100"`
- `"#1b5e20"`
- `"#8a1bba"`
- `"#f57f17"`
- `"#1b918a"`

Subsequence colors are not critically important, but it is a nice-to-have for similar subsequences across perspectives (e.g. input, processing, output) to have the same color.

**Code citations**

To improve auditability and reader confidence, add code citations to the end of step descriptions when applicable. The line numbers in these citations should be on, or very near, where the caller makes the call (the "caller" meaning the resource with control - it is the resource named in the most recent previous "to" or "restartAt" step, or "start" if there is no previous such step). Explained another way, if a step goes from resource X to resource Y, the cited line should correspond to where the caller (X) makes the call. A basic template will look like so:

```yaml
- to: AuditRepository
  label: Get audit status
  description: |
    <Prose description here>
    ##### <filePath>:<lineNumber>
```

`filePath` might look like "/pkg/dashboard/objects/releases.go", and `lineNumber` would just be an integer, naturally.

Add these citations only to steps coming from code-level resources (e.g. modules, classes) and only to the calling (outgoing) steps, not return steps.

Often, calls that are not function calls, but rather cross-boundry calls (e.g. HTTP calls) will be "constructed" in one location but actually dispatched in a helper function or module (e.g. "fetch()"). In these cases, cite the location where the call was constructed.

**Code Citation Links**

When the code repository is hosted in a repository with a web interface, add links to to the citation. Citations with links look like so:

```yaml
  # ...
  description: |
    <Prose description here>
    ##### [<filePath>:<lineNumber>](<repo url>/blob/<commit hash>/<filePath>#L<lineNumber>)
```

Discern the repo URL using the `git remote -v` command, if available. For instance, if the remote is hosted on GitHub, the repo url would be `https://github.com/<userName>/<repoName>`, such as "https://github.com/komodorio/helm-dashboard".

Discern the commit hash value using `git rev-parse --short HEAD`.


**Tips for well-structured sequence perspectives:**

- Sequence perspective names should start with a verb and be 2-4 words total (e.g. "Browse Release", "Update Chart").
- Always include return steps that pass control back to calling resources. This is analogous to process execution always returning up the "call stack." Avoid returns that "jump over" resources that have been called. Note that these kind of return steps aren't needed immediately after "toAsync" or "toAndBack" calls; the current control pointer doesn't change with "toAsync" and "toAndBack."
- Related to the above point, when documenting interactions between a user-driven front-end client and a backend, be sure to return results back to the user, and ensure all actions originate from the user. Keep the user in the loop.
- There is no hard limit for step counts in sequence perspectives. Some processes can involve a lot of steps. Generally aim to keep the total number of steps in a sequence perspective to under 200.
- Break each perspective into `subSequence` phases. Phases that are architecturally interesting (e.g. auth, fan-out) deserve their own phase. However, don't use a subsequence if the subsequence has fewer than three steps.
- Break up large subsequences into further subsequences (and, for very detailed processes, subsequences of those). A subsequence with more than 20 steps is a strong candidate to be broken down into one or more further subsequences.
- Keep each individual step label short (≤6 words). Put elaboration in `description:` (see below).
- Use plain English in the labels instead of literal function call names/SQL commands/etc. For instance instead of "INSERT source record", just say "Insert source record."
- "Forward" step labels should generally start with verbs ("Call..", "Get...", "Create..."), while "return" step labels should generally be nouns saying what was returned (if anything).
- Also use plain English as much as possible in the step descriptions. Generally avoid using function names, instead seek to explain the purpose of the step.
- Avoid using `toAndBack:`. Use `to:` steps to explicitly specify the control flow.
- Ensure every sequence's control returns to the "start" resource at least once. Similarly, for every "restartAt" ensure the sequence also returns to the specified resource at least once.
- Add `notes: |` on every `subSequence`. The notes should explain the *why*, not just the *what*.
- Use `restartAt` sparingly. Generally model control flow changes with explicit `to:` steps. `restartAt` is primarily used in highly asyncronous flows, such as if a resource performs an action on a timer (e.g. polling).
- Steps can go to the resource it originates from to show internal work being done. These are rendered in the diagram as an arrow pointing from a resource to itself.
- Give every step a one- or two-sentence `description:` — the label is a diagram caption, the description is what actually teaches the reader something. Skip it only on plain `color: gray` return-path hops with no new information.

---

#### Relation perspectives

Include at least these two:

**Class / type inheritance:**

```yaml
- name: Class Inheritance
  color: Firebrick
  orientation: topToBottom
  options:
    arrowDirection: backward
    defaultArrowLabel: Extends
  notes: |
    "Is a" relationships. Arrows point from superclass to subclass.
  relations:
  - from: BaseClass
    to: SubclassA, SubclassB
  - from: SubclassA
    to: ConcreteImpl
```

Use comma-separated `to:` when a superclass has multiple direct subclasses.

**Instantiation / ownership:**

```yaml
- name: Instantiation
  color: DarkRed
  defaultArrowLabel: Instantiates
  notes: |
    Which classes create instances of other classes.
  relations:
  - from: Orchestrator
    to: ServiceA, ServiceB, ServiceC
  - from: ServiceA
    to: HelperClass
```

**Don't draw relations between a resource and its own parent/child.** Ilograph already renders
the tree's containment nesting automatically wherever a descendant is referenced in a perspective — a module doesn't need an explicit relation to the classes it contains (skip `from: API Layer / to: Identity, Ciphers` if those are children of `API Layer`). Reserve relation perspectives for relationships the tree doesn't already show: cross-module dependencies, data ownership between sibling models, etc.

In the perspectives list, place all relation perspectives after the sequence perspectives.

---

#### Perspective list

In the very first perspective, and only in the very first perspective, add a perspective list called "Other Perspectives" to the end of the perspective's `notes:`. It should contain the names and a very short description of each perspective other than the first. The perspective names should be exact and wrapped in square brackets [like so]. The list should look like this:

```yaml
# ...
notes: |
  <Existing perspective notes>
  #### Other Perspectives
  [Second perspective name] - <very short description of the second perspective>

  [Third perspective name] - <very short description of the third perspective>

  ... and so on
```

### Citation reference

If code citations added to sequence steps included links, add one final reference to the repo url and commit hash at the very end of the yaml file. It should look like so:

```yaml
# PLEASE DO NOT REMOVE
# REPO URL: <repo url>
# COMMIT HASH: <commit hash>
```

## Phase 3 — Review checklist

Before finishing, verify:

- [ ] Every resource referenced in any perspective exists in the `resources:` section (check using script)
- [ ] Every resource in `resources:` appears in at least one perspective or has a descendant resource that appears in at least one perspective (prune anything that doesn't) (check using script)
- [ ] Every resource in `resources:` has a `name` with no restricted characters (/, ^, *, [, ], or commas), or, for resources that do have names with restricted characters, they also have an `id` without restricted characters, and these resources are referenced by `id` instead of `name` in perspectives.  (check using script)
- [ ] Every sequence's control returns to the "start" resource at least once. For every "restartAt", sequence also returns to the specified resource at least once. (check using script)
- [ ] No `restartAt` for control flow not related to background worker processing/polling/webhooks
- [ ] Synchronous `to:` steps pair up with matching returns: control returns one resource at a time back up the call stack, never jumping over a resource that was called and is still waiting (`toAsync:`/`toAndBack:` need no return) (check using script)
- [ ] Block scalar content (`description: |`, `notes: |`) is indented 2 spaces relative to its key — not collapsed to the key's level  (check using script)
- [ ] List dashes (`-`) are at the same column as their parent key (compact block sequence style)  (check using script)
- [ ] `subSequence` blocks have a `name:`, `color:`, `notes:`, and `steps:`  (check using script)
- [ ] Relation perspective entries with the same `from` are combined with comma-separated `to:` values if their other properties (label, description, color, etc.) are identical
- [ ] No relation connects a resource to its own parent or child (containment is already shown by the tree) (check using script)
- [ ] In sequence perspectives, every step with a `label` has a `description`, unless it's a plain `color: gray` return-path hop  (check using script)
- [ ] No `description`/`notes` paragraph has a hard line-wrap mid-sentence  (check using script)
- [ ] Code-level references (functions, enums, filenames, types) in `description`/`notes` are backticked; `label` values are left plain
- [ ] Relation perspectives are listed after sequence perspectives in the perspective list

Use the `validate_ilograph.py` script to check items marked with `(check using script)`

Write the completed YAML to `ilograph.yaml` in the current working directory. When finished, remind the user that the yaml can be used on the Ilograph web app (https://app.ilograph.com/new/) or Ilograph Desktop (https://www.ilograph.com/desktop/). In either case, they would want to create a new diagram and paste the YAML into the editor that appears on the left-hand side of the app.

Further refinements to the YAML could include creating sequence perspectives for specific processes/flows that the user requests.