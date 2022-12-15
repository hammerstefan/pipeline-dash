# Jobs File YAML

<!-- TOC -->
* [Jobs File YAML](#jobs-file-yaml)
  * [Overview](#overview)
  * [Details](#details)
    * [Job Options](#job-options)
<!-- TOC -->

## Overview
The `cli dash` command requires a `PIPELINE_CONFIG`, which is a YAML file that specifies the pipeline of jobs that you
want to collect data for and visualize.

The file consists of a mapping of servers and the pipelines on each of those servers.  Pipeline collections are defined
by and entry starting with a `.` (e.g. `.cool-project`). Collections with the same name (and hierachy) across multiple
servers are collected and displayed together.

If we take a simple example of the `cool-project` project, which has a pipeline split across two controllers:
```yaml
servers:
  "https:build-server-url.com/endpoint/":
    pipelines:
      .cool-project:
        "Cool-Project-Build":
            "Cool-Project-Package":
                "Cool-Project-Stage":
  "https:test-server-url.com/endpoint/":
    pipelines:
      .cool-project:
        "Cool-Project-Test":
          "Cool-Project-Promote":
```

This would generate a table view along the lines of this:

| Name                    | Serial   | Status   | Job    |
|-------------------------|----------|----------|--------|
| cool-project            | 101, 102 | UNSTABLE |        |
| ⊢ Cool-Project-Build    | 102      | SUCCESS  | [12]() |
|  ⊢ Cool-Project-Package | 102      | SUCCESS  | [10]() |
|   ⊢ Cool-Project-Stage  | 102      | UNSTABLE | [5]()  |
| ⊢ Cool-Project-Test     | 101      | SUCCESS  | [3]()  |
|  ⊢ Cool-Project-Promote | 101      | Not Run  |        |

And would generate a pipeline visualization along the lines of:

```text
cool-project ─┬─── Cool-Project-Build ──── Package ────── Stage
              │
              │
              └─── Cool-Project-Test ───── Promote
```

## Details
TODO provide more complex examples
### Job Options
* label - shortened display name to use on subway map