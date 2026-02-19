# Kubernetes Storage — Complete Hands-On Guide

> A beginner-friendly, detailed guide to persistent storage in Kubernetes using Volumes, PersistentVolumes (PV), PersistentVolumeClaims (PVC), and StorageClasses — with a real running demo app on Docker Desktop / Minikube.

---

## Table of Contents

1.  [The Problem: Why Do We Need Persistent Storage?](#1-the-problem-why-do-we-need-persistent-storage)
2.  [Volume Basics — Understanding the Building Blocks](#2-volume-basics--understanding-the-building-blocks)
    - [What Happens Without Volumes?](#21-what-happens-without-volumes)
    - [Volume Types Overview](#22-volume-types-overview)
3.  [emptyDir — Temporary Pod-level Storage](#3-emptydir--temporary-pod-level-storage)
4.  [hostPath — Node-level Storage (Dev/Test Only)](#4-hostpath--node-level-storage-devtest-only)
5.  [PersistentVolume (PV) — In Detail](#5-persistentvolume-pv--in-detail)
    - [What is a PV?](#51-what-is-a-pv)
    - [Access Modes](#52-access-modes)
    - [Reclaim Policies](#53-reclaim-policies)
    - [PV Lifecycle / Status](#54-pv-lifecycle--status)
6.  [PersistentVolumeClaim (PVC) — In Detail](#6-persistentvolumeclaim-pvc--in-detail)
    - [What is a PVC?](#61-what-is-a-pvc)
    - [How PVC Binds to PV](#62-how-pvc-binds-to-pv)
7.  [StorageClass — Dynamic Provisioning](#7-storageclass--dynamic-provisioning)
    - [What is a StorageClass?](#71-what-is-a-storageclass)
    - [How Dynamic Provisioning Works](#72-how-dynamic-provisioning-works)
8.  [PV vs PVC vs StorageClass — Side by Side](#8-pv-vs-pvc-vs-storageclass--side-by-side)
9.  [Hands-On Lab: Full Demo Walkthrough](#9-hands-on-lab-full-demo-walkthrough)
10. [How the Demo App Works](#10-how-the-demo-app-works)
11. [File-by-File YAML Explanation](#11-file-by-file-yaml-explanation)
12. [Useful Commands Cheat Sheet](#12-useful-commands-cheat-sheet)
13. [Common Mistakes & Troubleshooting](#13-common-mistakes--troubleshooting)
14. [Best Practices](#14-best-practices)

---

## 1. The Problem: Why Do We Need Persistent Storage?

Imagine you have a web app that lets users upload files, or a database running in Kubernetes:

```python
# ❌ BAD — Writing data inside the container filesystem
with open("/app/data/uploads/photo.jpg", "wb") as f:
    f.write(uploaded_file)
```

**What happens when the Pod restarts?**

```
 Pod Running        Pod Crashes/Restarts       New Pod Starts
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Container   │    │                  │    │  Container       │
│  /app/data/  │    │   💥 CRASH!      │    │  /app/data/      │
│   photo.jpg ✅│   │                  │    │   (EMPTY!) ❌    │
│   notes.txt ✅│   │  All data LOST!  │    │                  │
└──────────────┘    └──────────────────┘    └──────────────────┘
```

**Problems with container filesystem storage:**

| Problem | Why It's Bad |
| :--- | :--- |
| **Ephemeral by design** | Container filesystem is destroyed when the container stops |
| **No data sharing** | Two containers in the same Pod can't share files |
| **No persistence** | Database data, user uploads, logs — all gone after restart |
| **No portability** | Data is tied to a specific node's filesystem |

**The Kubernetes Solution — Volumes & Persistent Storage:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   Pod                                                               │
│   ┌───────────────────┐                                            │
│   │ Container         │                                            │
│   │ /app/data/ ───────┼─── volumeMount ───┐                       │
│   └───────────────────┘                    │                       │
│                                             ▼                       │
│                                     ┌──────────────┐               │
│                                     │   Volume      │               │
│                                     │  (in Pod spec)│               │
│                                     └──────┬───────┘               │
│                                            │                        │
│                    ┌───────────────────────┼──────────────────┐     │
│                    ▼                       ▼                  ▼     │
│              emptyDir              PersistentVolume        hostPath │
│           (temp, pod-life)        Claim (PVC)          (node disk) │
│                                        │                            │
│                                        ▼                            │
│                              PersistentVolume (PV)                  │
│                          (actual storage resource)                  │
│                                        │                            │
│                         ┌──────────────┼──────────────┐            │
│                         ▼              ▼              ▼            │
│                    Local Disk     Cloud Disk      NFS Share         │
│                   (hostPath)    (AWS EBS,        (Network)          │
│                                 GCP PD,                             │
│                                 Azure Disk)                         │
└─────────────────────────────────────────────────────────────────────┘
```

**Your app just reads/writes to a mount path — it doesn't care WHERE the storage actually is. Kubernetes handles the plumbing.**

---

## 2. Volume Basics — Understanding the Building Blocks

### 2.1 What Happens Without Volumes?

```bash
# Create a pod, write a file, then delete it
kubectl run test-pod --image=busybox -- sh -c "echo hello > /tmp/data.txt && sleep 3600"

# Check the file exists
kubectl exec test-pod -- cat /tmp/data.txt
# Output: hello

# Delete and recreate
kubectl delete pod test-pod
kubectl run test-pod --image=busybox -- sh -c "cat /tmp/data.txt; sleep 3600"

# File is GONE! ❌
kubectl exec test-pod -- cat /tmp/data.txt
# Output: cat: can't open '/tmp/data.txt': No such file or directory
```

### 2.2 Volume Types Overview

| Volume Type | Lifetime | Use Case | Persists After Pod Delete? |
| :--- | :--- | :--- | :--- |
| **emptyDir** | Same as Pod | Temp scratch space, caching, sharing between containers | ❌ No |
| **hostPath** | Same as Node | Dev/testing, accessing node-level files | ⚠️ On same node only |
| **PersistentVolumeClaim** | Independent | Databases, file uploads, any real data | ✅ Yes |
| **configMap / secret** | Same as object | Config files (covered in L3) | N/A |
| **nfs** | Independent | Shared storage across nodes | ✅ Yes |

---

## 3. emptyDir — Temporary Pod-level Storage

### What is emptyDir?

An `emptyDir` volume is created **when a Pod is assigned to a Node**. It starts **empty** and exists as long as the Pod runs. When the Pod is removed, the data is **permanently deleted**.

### When to Use emptyDir

- Scratch space for sorting / processing
- Sharing files between containers in the same Pod (sidecar pattern)
- Caching data that can be regenerated

### YAML Example

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-demo
spec:
  containers:
    # Container 1 — writes data
    - name: writer
      image: busybox
      command: ["sh", "-c"]
      args:
        - |
          while true; do
            echo "$(date) — Hello from writer" >> /shared/log.txt
            sleep 5
          done
      volumeMounts:
        - name: shared-data          # ← mount the volume
          mountPath: /shared          # ← path inside container

    # Container 2 — reads same data
    - name: reader
      image: busybox
      command: ["sh", "-c"]
      args:
        - |
          sleep 10
          tail -f /shared/log.txt
      volumeMounts:
        - name: shared-data          # ← same volume name
          mountPath: /shared          # ← can use different path

  volumes:
    - name: shared-data
      emptyDir: {}                    # ← empty directory, starts fresh
```

### Try It

```bash
kubectl apply -f 01-emptydir.yaml
kubectl logs emptydir-demo -c reader -f    # see shared data
kubectl delete pod emptydir-demo            # data is gone after this
```

### Visual Explanation

```
  Pod: emptydir-demo
  ┌─────────────────────────────────────────┐
  │                                         │
  │  ┌─────────┐       ┌─────────┐         │
  │  │ writer  │       │ reader  │         │
  │  │ /shared │       │ /shared │         │
  │  └────┬────┘       └────┬────┘         │
  │       │                 │               │
  │       └────────┬────────┘               │
  │                ▼                        │
  │        ┌──────────────┐                 │
  │        │  emptyDir    │                 │
  │        │  volume      │                 │
  │        │  (in memory  │                 │
  │        │   or disk)   │                 │
  │        └──────────────┘                 │
  │                                         │
  └─────────────────────────────────────────┘
         Pod deleted → Volume gone! 💨
```

---

## 4. hostPath — Node-level Storage (Dev/Test Only)

### What is hostPath?

A `hostPath` volume mounts a **file or directory from the host node's filesystem** into your Pod. The data persists on that specific node, but if the Pod moves to a different node, it won't find the data.

### ⚠️ Warning

`hostPath` is **NOT recommended for production**. Use it only for:
- Local development (Docker Desktop / Minikube)
- Accessing node-level system files (e.g., `/var/log`)
- Testing PV concepts before moving to cloud storage

### YAML Example

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-demo
spec:
  containers:
    - name: app
      image: busybox
      command: ["sh", "-c", "echo 'Persisted!' > /data/hello.txt && sleep 3600"]
      volumeMounts:
        - name: host-storage
          mountPath: /data               # ← path inside container
  volumes:
    - name: host-storage
      hostPath:
        path: /tmp/k8s-demo-data        # ← path on the HOST/NODE
        type: DirectoryOrCreate          # ← create dir if missing
```

### hostPath Types

| Type | Behavior |
| :--- | :--- |
| `""` (empty) | No checks, mount whatever is there |
| `DirectoryOrCreate` | Create directory if it doesn't exist |
| `Directory` | Directory must already exist |
| `FileOrCreate` | Create file if it doesn't exist |
| `File` | File must already exist |

---

## 5. PersistentVolume (PV) — In Detail

### 5.1 What is a PV?

A **PersistentVolume (PV)** is a piece of storage in the cluster that has been **provisioned by an administrator** (or dynamically via a StorageClass). It is a **cluster-level resource** — it exists independently of any Pod.

Think of it as a **"storage disk"** that Kubernetes manages:

```
                    Cluster
  ┌────────────────────────────────────────┐
  │                                        │
  │   PV: my-pv-1           PV: my-pv-2   │
  │   ┌────────────┐       ┌────────────┐ │
  │   │ 5Gi        │       │ 10Gi       │ │
  │   │ ReadWrite  │       │ ReadOnly   │ │
  │   │ Once       │       │ Many       │ │
  │   │ hostPath   │       │ nfs        │ │
  │   │ Available ✅│       │ Bound 🔗  │ │
  │   └────────────┘       └────────────┘ │
  │                                        │
  │   These exist INDEPENDENTLY of Pods    │
  │   (like a hard drive in a server room) │
  └────────────────────────────────────────┘
```

### PV YAML Example

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: my-local-pv
  labels:
    type: local
    env: demo
spec:
  capacity:
    storage: 1Gi                         # ← total size of this volume
  accessModes:
    - ReadWriteOnce                      # ← one node can read/write
  persistentVolumeReclaimPolicy: Retain  # ← keep data after PVC deleted
  storageClassName: manual               # ← for matching with PVCs
  hostPath:
    path: /tmp/k8s-pv-data              # ← actual path on the node
```

### 5.2 Access Modes

Access modes define **how** the volume can be mounted:

| Mode | Short | Meaning | Use Case |
| :--- | :--- | :--- | :--- |
| `ReadWriteOnce` | RWO | Read-write by **one node** | Databases (MySQL, Postgres) |
| `ReadOnlyMany` | ROX | Read-only by **many nodes** | Shared config, static assets |
| `ReadWriteMany` | RWX | Read-write by **many nodes** | Shared file uploads (NFS) |
| `ReadWriteOncePod` | RWOP | Read-write by **one pod** (K8s 1.22+) | Strict single-writer |

```
  ReadWriteOnce (RWO)              ReadOnlyMany (ROX)
  ┌──────────────────┐             ┌──────────────────┐
  │ Node A           │             │ Node A   Node B   │
  │ ┌──────┐         │             │ ┌──────┐┌──────┐ │
  │ │Pod 1 │ R/W ✅  │             │ │Pod 1 ││Pod 2 │ │
  │ └──────┘         │             │ │ R ✅  ││ R ✅  │ │
  │                  │             │ └──────┘└──────┘ │
  │ Node B           │             │ (Write ❌ by any) │
  │ ┌──────┐         │             └──────────────────┘
  │ │Pod 2 │ ❌ Can't│
  │ └──────┘  mount  │
  └──────────────────┘

  ReadWriteMany (RWX)
  ┌──────────────────┐
  │ Node A   Node B  │
  │ ┌──────┐┌──────┐ │
  │ │Pod 1 ││Pod 2 │ │
  │ │R/W ✅ ││R/W ✅ │ │
  │ └──────┘└──────┘ │
  │ (Requires NFS or │
  │  shared storage) │
  └──────────────────┘
```

### 5.3 Reclaim Policies

What happens to the PV **after the PVC using it is deleted**:

| Policy | What Happens | Use Case |
| :--- | :--- | :--- |
| `Retain` | PV and data kept; manual cleanup needed | Production — don't lose data |
| `Delete` | PV and underlying storage are deleted | Dev/test — auto cleanup |
| `Recycle` | Data wiped (`rm -rf /data/*`), PV reused | ⚠️ Deprecated — don't use |

```
  PVC Deleted → What happens to PV?

  Retain:                    Delete:
  ┌──────────────┐           ┌──────────────┐
  │ PV still     │           │ PV deleted   │
  │ exists ✅    │           │ entirely 🗑️ │
  │ Data kept ✅ │           │ Data gone ❌ │
  │ Status:      │           │              │
  │ "Released"   │           │              │
  │ (manual      │           │              │
  │  cleanup)    │           │              │
  └──────────────┘           └──────────────┘
```

### 5.4 PV Lifecycle / Status

```
  Available ──→ Bound ──→ Released ──→ (Recycle/Delete or manual cleanup)
      │            │           │
      │            │           └── PVC was deleted but PV still exists
      │            └── PVC has claimed this PV
      └── PV is ready and waiting for a PVC
```

| Status | Meaning |
| :--- | :--- |
| `Available` | Free, not bound to any PVC |
| `Bound` | Linked to a PVC |
| `Released` | PVC deleted, but PV not yet reclaimed |
| `Failed` | Automatic reclamation failed |

---

## 6. PersistentVolumeClaim (PVC) — In Detail

### 6.1 What is a PVC?

A **PersistentVolumeClaim (PVC)** is a **request for storage** by a user/Pod. It's like saying:

> "I need 500Mi of read-write storage. Kubernetes, please find or create it for me."

The PVC is the **bridge** between your Pod and the actual storage (PV):

```
  Pod                    PVC                      PV
  ┌──────────┐          ┌──────────────┐         ┌──────────────┐
  │          │  mounts  │ "I need      │  binds  │ Actual       │
  │ /app/data├─────────→│  500Mi RWO"  ├────────→│ Storage      │
  │          │          │              │         │ 1Gi hostPath │
  └──────────┘          └──────────────┘         └──────────────┘
   (User's app)          (Request)                (Resource)
```

### PVC YAML Example

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  accessModes:
    - ReadWriteOnce                  # ← must match PV's access mode
  resources:
    requests:
      storage: 500Mi                 # ← I need at least this much
  storageClassName: manual           # ← must match PV's storageClassName
```

### 6.2 How PVC Binds to PV

Kubernetes matches a PVC to a PV based on:

1. **StorageClassName** — must match (or both empty)
2. **Access Mode** — PV must support the requested mode
3. **Capacity** — PV size ≥ PVC requested size
4. **Labels/Selectors** — optional, for specific PV targeting

```
  PVC Request:                    Available PVs:
  ┌────────────────────┐
  │ storageClass: manual│         PV-1: manual, RWO, 5Gi  → ✅ MATCH!
  │ accessMode: RWO    │         PV-2: fast,   RWO, 10Gi → ❌ wrong class
  │ storage: 500Mi     │         PV-3: manual, ROX, 1Gi  → ❌ wrong mode
  └────────────────────┘
                                  PVC binds to PV-1 ✅
                                  (500Mi requested, 5Gi available — OK)
```

### Using a PVC in a Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  containers:
    - name: app
      image: my-app:v1
      volumeMounts:
        - name: data-volume
          mountPath: /app/data              # ← path inside container
  volumes:
    - name: data-volume
      persistentVolumeClaim:
        claimName: my-pvc                   # ← reference the PVC name
```

---

## 7. StorageClass — Dynamic Provisioning

### 7.1 What is a StorageClass?

A **StorageClass** tells Kubernetes **how** to dynamically create PVs when a PVC is made. Instead of an admin manually creating PVs, the StorageClass acts as a "template" for auto-provisioning.

```
  WITHOUT StorageClass (Static):          WITH StorageClass (Dynamic):
  ┌─────────────────────────────┐         ┌─────────────────────────────┐
  │                             │         │                             │
  │  Admin creates PV manually  │         │  1. Admin creates           │
  │  ↓                          │         │     StorageClass            │
  │  User creates PVC           │         │  2. User creates PVC       │
  │  ↓                          │         │     (references class)      │
  │  Kubernetes binds PVC → PV  │         │  3. Kubernetes AUTO-creates │
  │                             │         │     PV and binds it!        │
  └─────────────────────────────┘         └─────────────────────────────┘
```

### StorageClass YAML Example

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-storage
provisioner: k8s.io/minikube-hostpath   # ← who creates the storage
reclaimPolicy: Delete                    # ← what happens when PVC deleted
volumeBindingMode: Immediate             # ← when to bind PV to PVC
allowVolumeExpansion: true               # ← can PVC grow later?
```

### 7.2 How Dynamic Provisioning Works

```
  Step 1: StorageClass exists            Step 2: User creates PVC
  ┌──────────────────────┐              ┌──────────────────────┐
  │ StorageClass: fast   │              │ PVC: my-claim        │
  │ provisioner: hostpath│◄─────────────│ storageClass: fast   │
  │ reclaimPolicy: Delete│  references  │ storage: 1Gi         │
  └──────────────────────┘              └──────────────────────┘

  Step 3: K8s auto-creates PV           Step 4: PVC bound, Pod uses it
  ┌──────────────────────┐              ┌──────────────────────┐
  │ PV: pvc-abc123       │              │ Pod                  │
  │ 1Gi, RWO             │◄─────────────│  └─ volumeMount:     │
  │ (auto-provisioned!)  │   bound      │      /app/data →PVC  │
  └──────────────────────┘              └──────────────────────┘
```

### Default StorageClass

Most Kubernetes setups have a **default** StorageClass. If your PVC doesn't specify a `storageClassName`, the default is used:

```bash
# Check default StorageClass
kubectl get storageclass
# NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE
# hostpath (default)   docker.io/hostpath         Delete          Immediate
```

Docker Desktop default: `hostpath`
Minikube default: `standard` (uses `k8s.io/minikube-hostpath`)

### PVC with Dynamic Provisioning (No Manual PV Needed!)

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dynamic-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: hostpath        # ← use this StorageClass
  # OR omit storageClassName to use the default class
```

When you apply this PVC, Kubernetes **automatically creates a PV** for you!

---

## 8. PV vs PVC vs StorageClass — Side by Side

| Aspect | PersistentVolume (PV) | PersistentVolumeClaim (PVC) | StorageClass (SC) |
| :--- | :--- | :--- | :--- |
| **What is it?** | Actual storage resource | Request for storage | Template for auto-creating PVs |
| **Who creates it?** | Admin (or auto by SC) | Developer / App | Admin |
| **Scope** | Cluster-wide | Namespace-scoped | Cluster-wide |
| **Analogy** | Hard drive in server room | "I need a 500GB drive" | "Use SSD drives from AWS" |
| **Required?** | Yes (manual or auto) | Yes (to use PV in Pod) | No (only for dynamic) |

### The Full Flow

```
  ┌───────────────────────────────────────────────────────────────────┐
  │                                                                   │
  │  STATIC PROVISIONING              DYNAMIC PROVISIONING            │
  │                                                                   │
  │  Admin → PV (manual)              Admin → StorageClass            │
  │           ↓                                  ↓                    │
  │  Dev → PVC (bind to PV)           Dev → PVC (references SC)      │
  │         ↓                                  ↓                      │
  │  Pod → uses PVC                   K8s → auto-creates PV          │
  │                                          ↓                        │
  │                                   Pod → uses PVC                  │
  └───────────────────────────────────────────────────────────────────┘
```

---

## 9. Hands-On Lab: Full Demo Walkthrough

### Prerequisites

- Docker Desktop with Kubernetes enabled **OR** Minikube running
- `kubectl` configured and working

```bash
# Verify your setup
kubectl cluster-info
kubectl get nodes
```

### Step 1: Build the Demo App Image

```bash
# Navigate to the app directory
cd L4_Storage/app

# Build the Docker image
docker build -t storage-demo-app:v1 .

# Verify
docker images | grep storage-demo
```

### Step 2: Apply All Manifests (Individual Files)

```bash
cd ../manifests

# ── Phase 1: emptyDir example ──
kubectl apply -f 01-emptydir.yaml
kubectl logs emptydir-demo -c reader     # wait a few seconds, then check

# ── Phase 2: hostPath example ──
kubectl apply -f 02-hostpath.yaml
kubectl exec hostpath-demo -- cat /data/hello.txt

# ── Phase 3: Static PV + PVC ──
kubectl apply -f 03-pv-hostpath.yaml
kubectl apply -f 04-pvc-static.yaml
kubectl get pv,pvc                       # check binding

# ── Phase 4: Dynamic PVC ──
kubectl apply -f 05-pvc-dynamic.yaml
kubectl get pv,pvc                       # new PV auto-created!

# ── Phase 5: Full Demo App with Storage ──
kubectl apply -f 06-deployment-storage.yaml
kubectl apply -f 07-service.yaml

# Wait for pod to be ready
kubectl get pods -l app=storage-demo -w

# Access the app
# http://localhost:30081
```

### Step 3: Or Apply Everything at Once

```bash
kubectl apply -f all-in-one.yaml

# Access the app at http://localhost:30081
```

### Step 4: Test Persistence!

This is the **key experiment** to prove storage works:

```bash
# 1. Write data to the app
curl -X POST "http://localhost:30081/write?filename=test.txt&content=HelloWorld"

# 2. Read data back
curl "http://localhost:30081/read?filename=test.txt"
# Output: HelloWorld ✅

# 3. Delete the pod (simulate a crash)
kubectl delete pod -l app=storage-demo

# 4. Wait for the new pod to start
kubectl get pods -l app=storage-demo -w

# 5. Read data again — it's STILL there!
curl "http://localhost:30081/read?filename=test.txt"
# Output: HelloWorld ✅  ← Data survived the pod restart!
```

### Step 5: Cleanup

```bash
# Delete everything
kubectl delete -f all-in-one.yaml

# Or individual cleanup
kubectl delete -f 07-service.yaml
kubectl delete -f 06-deployment-storage.yaml
kubectl delete -f 05-pvc-dynamic.yaml
kubectl delete -f 04-pvc-static.yaml
kubectl delete -f 03-pv-hostpath.yaml
kubectl delete -f 02-hostpath.yaml
kubectl delete -f 01-emptydir.yaml
```

---

## 10. How the Demo App Works

The demo app is a **FastAPI** application that demonstrates storage by providing endpoints to **write**, **read**, **list**, and **delete** files on a mounted volume.

```
              Browser / curl
                   │
                   ▼
         ┌──────────────────┐
         │  FastAPI App      │
         │  (Port 8000)      │
         │                   │
         │  GET  /           │ → Dashboard showing storage info
         │  POST /write      │ → Write a file to storage
         │  GET  /read       │ → Read a file from storage
         │  GET  /list       │ → List all files in storage
         │  DELETE /delete   │ → Delete a file from storage
         │  GET  /health     │ → Health check
         │                   │
         │  /app/data/ ──────┼───→ PVC Mount (persistent!)
         └──────────────────┘
```

### Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/` | HTML dashboard with storage info |
| POST | `/write?filename=X&content=Y` | Write content to a file |
| GET | `/read?filename=X` | Read a file |
| GET | `/list` | List all files in storage |
| DELETE | `/delete?filename=X` | Delete a file |
| GET | `/health` | App health + storage status |

---

## 11. File-by-File YAML Explanation

### `01-emptydir.yaml` — emptyDir Volume Demo

Two containers sharing an emptyDir volume. Writer writes timestamps, reader tails the log. Data is lost when Pod is deleted.

### `02-hostpath.yaml` — hostPath Volume Demo

A Pod that writes to a hostPath volume. Data persists on the node even after Pod deletion, but is only accessible from that specific node.

### `03-pv-hostpath.yaml` — PersistentVolume (Static)

Manually created PV using hostPath. This represents the **admin provisioning** a storage resource with 1Gi capacity, RWO access, and Retain policy.

### `04-pvc-static.yaml` — PVC Bound to Static PV

A PVC that requests 500Mi and matches to the PV via `storageClassName: manual`. Kubernetes binds them together.

### `05-pvc-dynamic.yaml` — PVC with Dynamic Provisioning

A PVC that uses the default StorageClass. No manual PV needed — Kubernetes creates one automatically!

### `06-deployment-storage.yaml` — Deployment Using PVC

A Deployment that mounts the dynamic PVC at `/app/data`. The demo app reads/writes files there. Data survives pod restarts and redeployments.

### `07-service.yaml` — NodePort Service

Exposes the app on port `30081` so you can access it from your browser.

### `all-in-one.yaml` — Everything Combined

All resources in a single file for quick setup. Uses dynamic provisioning for simplicity.

---

## 12. Useful Commands Cheat Sheet

### PersistentVolume Commands

```bash
# List all PVs
kubectl get pv

# Detailed PV info
kubectl describe pv <pv-name>

# Watch PV status changes
kubectl get pv -w

# Get PVs in wide format (shows more columns)
kubectl get pv -o wide

# Delete a PV
kubectl delete pv <pv-name>
```

### PersistentVolumeClaim Commands

```bash
# List all PVCs (in current namespace)
kubectl get pvc

# Detailed PVC info
kubectl describe pvc <pvc-name>

# See which PV a PVC is bound to
kubectl get pvc <pvc-name> -o jsonpath='{.spec.volumeName}'

# Delete a PVC (may delete PV depending on reclaim policy!)
kubectl delete pvc <pvc-name>
```

### StorageClass Commands

```bash
# List all StorageClasses
kubectl get storageclass
kubectl get sc            # shorthand

# See the default StorageClass (has "default" annotation)
kubectl get sc -o wide

# Describe a StorageClass
kubectl describe sc <name>
```

### Debugging Storage Issues

```bash
# Check if PVC is bound
kubectl get pvc
# STATUS should be "Bound" ✅

# Check PV binding
kubectl get pv
# STATUS should be "Bound" ✅

# See events (helpful for binding failures)
kubectl describe pvc <pvc-name> | grep -A 10 Events

# Check pod mount issues
kubectl describe pod <pod-name> | grep -A 20 Volumes

# Exec into pod to verify mount
kubectl exec -it <pod-name> -- ls -la /app/data
kubectl exec -it <pod-name> -- df -h /app/data
```

---

## 13. Common Mistakes & Troubleshooting

### ❌ PVC Stuck in `Pending` State

```bash
kubectl get pvc
# NAME     STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS
# my-pvc   Pending                                       manual
```

**Causes & Fixes:**

| Cause | Fix |
| :--- | :--- |
| No matching PV exists | Create a PV with matching `storageClassName`, `accessMode`, and enough `capacity` |
| StorageClass doesn't exist | Check `kubectl get sc` — create the SC or fix the name |
| No default StorageClass | Set one: `kubectl annotate sc <name> storageclass.kubernetes.io/is-default-class=true` |
| Capacity mismatch | PV size must be ≥ PVC request |
| Access mode mismatch | PV must support the access mode PVC requests |

```bash
# Debug: Check events for reason
kubectl describe pvc my-pvc
# Events:
#   Warning  ProvisioningFailed  ... no persistent volumes available for this claim
```

### ❌ Pod Can't Start — Volume Mount Error

```bash
kubectl describe pod <pod-name>
# Warning  FailedMount  Unable to attach or mount volumes
```

**Causes & Fixes:**

| Cause | Fix |
| :--- | :--- |
| PVC not bound yet | Wait for PVC to bind: `kubectl get pvc -w` |
| Wrong `claimName` | Verify PVC name matches in Pod spec |
| hostPath doesn't exist | Use `type: DirectoryOrCreate` or create the directory |
| RWO volume already mounted on different node | Use `ReadWriteMany` or schedule pod on same node |

### ❌ Data Lost After Pod Restart

| What You Used | Expected? |
| :--- | :--- |
| `emptyDir` | ✅ Yes — emptyDir is destroyed with the Pod |
| `hostPath` without PV | ⚠️ Maybe — only if pod respawns on same node |
| PVC with `Delete` policy | ✅ Yes — if you deleted the PVC, PV is gone too |
| PVC with `Retain` policy | ❌ No — data should persist. Check mount path |

### ❌ PV Shows "Released" After PVC Delete

```bash
kubectl get pv
# NAME       CAPACITY   STATUS     RECLAIM POLICY
# my-pv      1Gi        Released   Retain
```

A Released PV cannot be rebound to a new PVC automatically. To reuse:

```bash
# Option 1: Delete and recreate the PV
kubectl delete pv my-pv
kubectl apply -f 03-pv-hostpath.yaml

# Option 2: Edit the PV to remove the claimRef
kubectl patch pv my-pv -p '{"spec":{"claimRef": null}}'
```

---

## 14. Best Practices

### Do ✅

| Practice | Why |
| :--- | :--- |
| Use **PVCs**, not direct volumes | Decouples app from storage implementation |
| Use **StorageClasses** for dynamic provisioning | Eliminates manual PV management |
| Set appropriate **reclaim policies** | `Retain` for prod, `Delete` for dev |
| Use **resource requests** in PVCs | Ensures you get enough storage |
| Label your PVs | Easier management: `kubectl get pv -l env=prod` |
| Monitor storage usage | Prevent full disks with alerts |
| Test persistence | Delete pods and verify data survives |

### Don't ❌

| Anti-Pattern | Why It's Bad |
| :--- | :--- |
| `hostPath` in production | Ties data to one node, no fault tolerance |
| Hardcode storage paths in app | Makes app non-portable |
| `Delete` reclaim policy for production data | Accidentally deleting PVC = data loss |
| Skip `accessMode` planning | Wrong mode = mounting failures |
| Ignore PVC `Pending` status | Pod will hang forever until PVC binds |
| Use `emptyDir` for important data | Data vanishes with the Pod |

### Storage Decision Tree

```
  Do I need persistent data?
       │
       ├── NO → Use emptyDir (temp scratch space)
       │
       └── YES
            │
            ├── Is it for local dev/test only?
            │     │
            │     ├── YES → Use hostPath (simple, node-local)
            │     │
            │     └── NO → Use PVC with StorageClass
            │                │
            │                ├── Single writer? → RWO (ReadWriteOnce)
            │                ├── Multiple readers? → ROX (ReadOnlyMany)
            │                └── Multiple writers? → RWX (ReadWriteMany + NFS)
            │
            └── Is it cloud?
                  │
                  ├── AWS → gp3/gp2 EBS StorageClass
                  ├── GCP → pd-standard/pd-ssd StorageClass
                  └── Azure → managed-premium StorageClass
```

---

## Appendix: Key Terminology Quick Reference

| Term | One-Line Definition |
| :--- | :--- |
| **Volume** | A directory accessible to containers in a Pod |
| **emptyDir** | Temporary volume that lives and dies with the Pod |
| **hostPath** | Mounts a path from the node's filesystem into a Pod |
| **PersistentVolume (PV)** | A provisioned piece of storage in the cluster |
| **PersistentVolumeClaim (PVC)** | A request for storage by a Pod |
| **StorageClass (SC)** | A template for dynamically provisioning PVs |
| **Static Provisioning** | Admin manually creates PVs before PVCs |
| **Dynamic Provisioning** | Kubernetes auto-creates PVs via StorageClass |
| **Access Mode** | Who can read/write (RWO, ROX, RWX, RWOP) |
| **Reclaim Policy** | What happens to PV when PVC is deleted (Retain/Delete) |
| **Binding** | The process of matching a PVC to a PV |
| **Capacity** | How much storage a PV provides or PVC requests |
