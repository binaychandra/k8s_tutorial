# Kubernetes Jobs & CronJobs – Beginner Guide (Minikube Friendly)

**Last updated:** February 2026  
**Goal:** Understand and run one-time tasks (Jobs) and scheduled/recurring tasks (CronJobs) on your local Minikube cluster.

## What are Jobs and CronJobs?

| Feature          | Job                              | CronJob                                   |
|------------------|----------------------------------|--------------------------------------------|
| Purpose          | Run a task **once** (or few times) until it finishes successfully | Run a Job **on a schedule** (like Linux cron) |
| Typical use      | Data processing, ML training (one run), database migration, batch conversion | Nightly backup, report generation, clean old files every hour/day, send weekly emails |
| Stops after?     | Yes – once done, Pods are terminated (but history remains) | No – keeps creating new Jobs forever (or until deleted) |
| API version (2026) | `batch/v1`                       | `batch/v1`                                 |

Both live in the `batch` API group.

## Important Restart Policies (very important!)

| restartPolicy | Meaning                                      | Use with          |
|---------------|----------------------------------------------|-------------------|
| **Never**     | If container fails → don't restart it        | Jobs (most common) |
| **OnFailure** | If container fails → Kubernetes restarts it  | Jobs & CronJobs   |
| **Always**    | Restart forever (like Deployments)           | **Never** use with Jobs/CronJobs! |

→ Almost always use **`Never`** or **`OnFailure`** for Jobs/CronJobs.

## 1. Simple Job Example – "Hello Job"

This job prints a message and finishes.

### hello-job.yaml

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: hello-job
spec:
  template:
    spec:
      containers:
      - name: hello
        image: busybox:1.35   # very small & useful image
        command: ["echo", "Hello from Kubernetes Job! Finished at $(date)"]
      restartPolicy: Never
  backoffLimit: 3          # retry up to 3 times if it fails
