# Reference

pyado provides two layers:

- **OOP API** (`pyado.oop`) — object-oriented resource wrappers; the
  recommended entry point for most applications.
- **Raw API** (`pyado.raw`) — one thin HTTP wrapper per ADO endpoint; useful
  for advanced use-cases or scripting without the OOP layer.

**See also:**
[Usage guide with worked examples](usage.md) ·
[Alternatives comparison](alternatives.md) ·
[Contributor guide](contributing.md)

---

## OOP API

### Service

```{eval-rst}
.. automodule:: pyado.oop.service
   :members:
```

### Organization

```{eval-rst}
.. automodule:: pyado.oop.organization
   :members:
```

### Process

```{eval-rst}
.. automodule:: pyado.oop.core.process
   :members:
```

### Project

```{eval-rst}
.. automodule:: pyado.oop.project
   :members:
```

### Settings

```{eval-rst}
.. automodule:: pyado.oop.settings
   :members:
```

#### Service Endpoint

```{eval-rst}
.. automodule:: pyado.oop.settings.service_endpoint
   :members:
```

### Search

```{eval-rst}
.. automodule:: pyado.oop.core.search
   :members:
```

### Repos

```{eval-rst}
.. automodule:: pyado.oop.repos
   :members:
```

#### Repository

```{eval-rst}
.. automodule:: pyado.oop.repos.repository
   :members:
   :no-index:
```

#### Pull Request

```{eval-rst}
.. automodule:: pyado.oop.repos.pull_request
   :members:
   :no-index:
```

#### Branch

```{eval-rst}
.. automodule:: pyado.oop.repos.branch
   :members:
```

#### Tag

```{eval-rst}
.. automodule:: pyado.oop.repos.tag
   :members:
```

#### Commit

```{eval-rst}
.. automodule:: pyado.oop.repos.commit
   :members:
   :no-index:
```

#### File Changes

```{eval-rst}
.. automodule:: pyado.oop.repos.file_change
   :members:
```

#### Policy Configuration

```{eval-rst}
.. automodule:: pyado.oop.repos.policy
   :members:
```

#### Policy Types

```{eval-rst}
.. automodule:: pyado.oop.repos.policy_types
   :members:
```

### Overview

```{eval-rst}
.. automodule:: pyado.oop.overview
   :members:
```

#### Dashboard

```{eval-rst}
.. automodule:: pyado.oop.overview.dashboard
   :members:
```

#### Wiki

```{eval-rst}
.. automodule:: pyado.oop.overview.wiki
   :members:
```

### Boards

```{eval-rst}
.. automodule:: pyado.oop.boards
   :members:
```

#### Work Item

```{eval-rst}
.. automodule:: pyado.oop.boards.work_item
   :members:
   :no-index:
```

#### Iteration

```{eval-rst}
.. automodule:: pyado.oop.boards.iteration
   :members:
```

#### Area

```{eval-rst}
.. automodule:: pyado.oop.boards.area
   :members:
```

#### Work Item Type

```{eval-rst}
.. automodule:: pyado.oop.boards.work_item_type
   :members:
```

### Pipelines

```{eval-rst}
.. automodule:: pyado.oop.pipelines
   :members:
```

#### Build

```{eval-rst}
.. automodule:: pyado.oop.pipelines.build
   :members:
   :no-index:
```

#### Build Timeline

```{eval-rst}
.. automodule:: pyado.oop.pipelines.build_timeline
   :members:
   :no-index:
```

#### Pipeline

```{eval-rst}
.. automodule:: pyado.oop.pipelines.pipeline
   :members:
```

#### Environment

```{eval-rst}
.. automodule:: pyado.oop.pipelines.environment
   :members:
```

#### Agent

```{eval-rst}
.. automodule:: pyado.oop.pipelines.agent
   :members:
```

#### Variable Group

```{eval-rst}
.. automodule:: pyado.oop.pipelines.variable_group
   :members:
```

#### Secure File

```{eval-rst}
.. automodule:: pyado.oop.pipelines.secure_file
   :members:
```

#### Task Group

```{eval-rst}
.. automodule:: pyado.oop.pipelines.task_group
   :members:
```

#### Distributed Task Session

```{eval-rst}
.. automodule:: pyado.oop.pipelines.distributed_task_session
   :members:
   :no-index:
```

---

## Raw API

### Core

```{eval-rst}
.. automodule:: pyado.raw._core
   :members:
```

### Profile

```{eval-rst}
.. automodule:: pyado.raw.core.profile
   :members:
```

### Project

```{eval-rst}
.. automodule:: pyado.raw.core.project
   :members:
```

### Identity

```{eval-rst}
.. automodule:: pyado.raw.core.identity
   :members:
```

### Dashboard

```{eval-rst}
.. automodule:: pyado.raw.overview.dashboard
   :members:
```

### Notification

```{eval-rst}
.. automodule:: pyado.raw.settings.notification
   :members:
```

### Policy

```{eval-rst}
.. automodule:: pyado.raw.repos.policy
   :members:
```

### Process

```{eval-rst}
.. automodule:: pyado.raw.core.process
   :members:
```

### Search

```{eval-rst}
.. automodule:: pyado.raw.core.search
   :members:
```

### Hook

```{eval-rst}
.. automodule:: pyado.raw.settings.hook
   :members:
```

### Service Endpoint

```{eval-rst}
.. automodule:: pyado.raw.settings.service_endpoint
   :members:
```

### Wiki

```{eval-rst}
.. automodule:: pyado.raw.overview.wiki
   :members:
```

### Repos

#### Git

```{eval-rst}
.. automodule:: pyado.raw.repos.git
   :members:
```

#### Pull Request

```{eval-rst}
.. automodule:: pyado.raw.repos.pull_request
   :members:
```

### Boards

#### Work Item

```{eval-rst}
.. automodule:: pyado.raw.boards.work_item
   :members:
```

### Pipelines

#### Build

```{eval-rst}
.. automodule:: pyado.raw.pipelines.build
   :members:
```

#### Pipeline

```{eval-rst}
.. automodule:: pyado.raw.pipelines.pipeline
   :members:
```

#### Task Group

```{eval-rst}
.. automodule:: pyado.raw.pipelines.task_group
   :members:
```

#### Agent

```{eval-rst}
.. automodule:: pyado.raw.pipelines.agent
   :members:
```

#### Environment

```{eval-rst}
.. automodule:: pyado.raw.pipelines.environment
   :members:
```

#### Variable Group

```{eval-rst}
.. automodule:: pyado.raw.pipelines.variable_group
   :members:
```

#### Secure File

```{eval-rst}
.. automodule:: pyado.raw.pipelines.secure_file
   :members:
```
