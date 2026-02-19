# L4 Storage — Local Setup Guide

> Step-by-step instructions to run the Storage demo on **Docker Desktop** or **Minikube** on your local machine.

---

## Prerequisites

| Tool | Check Command | Install |
| :--- | :--- | :--- |
| Docker Desktop | `docker version` | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |
| kubectl | `kubectl version --client` | Bundled with Docker Desktop, or [install separately](https://kubernetes.io/docs/tasks/tools/) |
| Kubernetes (local) | `kubectl cluster-info` | Enable in Docker Desktop Settings → Kubernetes → ✅ Enable |

---

## Option A: Docker Desktop (Recommended for Windows/Mac)

### Step 1: Enable Kubernetes

1. Open **Docker Desktop** → ⚙️ **Settings**
2. Go to **Kubernetes** tab
3. Check ✅ **Enable Kubernetes**
4. Click **Apply & Restart**
5. Wait for the green "Kubernetes running" indicator

```powershell
# Verify Kubernetes is running
kubectl cluster-info
# Output should show: Kubernetes control plane is running at https://...

kubectl get nodes
# Output: docker-desktop   Ready   control-plane   ...
```

### Step 2: Check Default StorageClass

```powershell
kubectl get storageclass
# NAME                 PROVISIONER          RECLAIMPOLICY   VOLUMEBINDINGMODE
# hostpath (default)   docker.io/hostpath   Delete          Immediate
```

You should see `hostpath` marked as `(default)`. This means dynamic provisioning will work automatically!

### Step 3: Build the Demo App Image

```powershell
# Navigate to the app directory
cd L4_Storage/app

# Build the Docker image
docker build -t storage-demo-app:v1 .

# Verify the image was created
docker images | Select-String "storage-demo"
```

> **Why no push?** Docker Desktop shares the image registry between Docker and the local Kubernetes cluster, so the image is immediately available.

### Step 4: Deploy Everything

```powershell
# Go to the manifests directory
cd ..\manifests

# Apply the all-in-one manifest
kubectl apply -f all-in-one.yaml

# Watch the pod come up
kubectl get pods -l app=storage-demo -w
# Wait for STATUS = Running, READY = 1/1
# Press Ctrl+C to stop watching
```

### Step 5: Verify Storage

```powershell
# Check PVC is bound
kubectl get pvc
# NAME               STATUS   VOLUME            CAPACITY   ACCESS MODES   STORAGECLASS
# storage-demo-pvc   Bound    pvc-xxxxxxxx      256Mi      RWO            hostpath

# Check auto-created PV
kubectl get pv
# NAME             CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM
# pvc-xxxxxxxx     256Mi      RWO            Delete           Bound    default/storage-demo-pvc
```

### Step 6: Access the App

Open your browser: **http://localhost:30081**

Or use curl:
```powershell
# Health check
curl http://localhost:30081/health

# Write a file
curl "http://localhost:30081/write?filename=hello.txt&content=HelloKubernetes"

# Read it back
curl "http://localhost:30081/read?filename=hello.txt"

# List all files
curl http://localhost:30081/list
```

### Step 7: Test Persistence (The Key Experiment!)

```powershell
# 1. Write a file
curl "http://localhost:30081/write?filename=persist-test.txt&content=This+should+survive"

# 2. Confirm it exists
curl "http://localhost:30081/read?filename=persist-test.txt"
# → "This should survive"

# 3. Delete the pod (simulating a crash)
kubectl delete pod -l app=storage-demo
# pod "storage-demo-xxxxxxxx-xxxxx" deleted

# 4. Wait for new pod (Deployment auto-recreates it)
kubectl get pods -l app=storage-demo -w
# Wait for READY 1/1

# 5. Read the file again — IT'S STILL THERE! 🎉
curl "http://localhost:30081/read?filename=persist-test.txt"
# → "This should survive"

# 6. Check restart history on the dashboard
# Open http://localhost:30081 — you'll see TWO entries in the restart log
```

### Step 8: Cleanup

```powershell
kubectl delete -f all-in-one.yaml
```

---

## Option B: Minikube

### Step 1: Install & Start Minikube

```powershell
# Install minikube (if not installed)
# Option 1: Using Chocolatey
choco install minikube

# Option 2: Using winget
winget install Kubernetes.minikube

# Start minikube
minikube start --driver=docker

# Verify
kubectl cluster-info
kubectl get nodes
```

### Step 2: Check Default StorageClass

```powershell
kubectl get storageclass
# NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE
# standard (default)   k8s.io/minikube-hostpath   Delete          Immediate
```

### Step 3: Build Image Inside Minikube

Minikube has its own Docker daemon. You need to build the image there:

```powershell
# Point your shell to minikube's Docker daemon
# For PowerShell:
& minikube -p minikube docker-env --shell powershell | Invoke-Expression

# Build the image (now builds INSIDE minikube)
cd L4_Storage/app
docker build -t storage-demo-app:v1 .

# Verify
docker images | Select-String "storage-demo"
```

### Step 4: Deploy & Access

```powershell
cd ..\manifests
kubectl apply -f all-in-one.yaml

# Wait for pod
kubectl get pods -l app=storage-demo -w

# Access via minikube service (opens browser automatically)
minikube service storage-demo-service

# Or get the URL
minikube service storage-demo-service --url
```

### Step 5: Cleanup

```powershell
kubectl delete -f all-in-one.yaml
minikube stop        # stop the cluster
# minikube delete    # fully remove (optional)
```

---

## Exploring Individual Manifests (Step by Step)

Instead of `all-in-one.yaml`, you can apply each file individually to understand each concept:

### Experiment 1: emptyDir (Temporary Storage)

```powershell
kubectl apply -f 01-emptydir.yaml

# Watch the reader container read shared data
kubectl logs emptydir-demo -c reader -f
# You should see timestamps written by the writer container

# Cleanup — all data is lost!
kubectl delete -f 01-emptydir.yaml
```

**Lesson:** emptyDir is temporary. Data is gone when the Pod is deleted.

### Experiment 2: hostPath (Node Storage)

```powershell
kubectl apply -f 02-hostpath.yaml

# Check the file was written
kubectl exec hostpath-demo -- cat /data/hello.txt

# Delete the pod
kubectl delete pod hostpath-demo

# Recreate it — data is still there on the node!
kubectl apply -f 02-hostpath.yaml
kubectl exec hostpath-demo -- cat /data/hello.txt
# → Still shows the data! (it's on the node's /tmp/k8s-hostpath-demo)

# Cleanup
kubectl delete -f 02-hostpath.yaml
```

**Lesson:** hostPath persists on the node, but is tied to that specific node.

### Experiment 3: Static PV + PVC (Manual Provisioning)

```powershell
# Step 1: Create the PV (admin's job)
kubectl apply -f 03-pv-hostpath.yaml
kubectl get pv
# STATUS: Available ← waiting for a claim

# Step 2: Create the PVC (developer's job)
kubectl apply -f 04-pvc-static.yaml
kubectl get pv,pvc
# Both should show STATUS: Bound ← matched!

# Step 3: Inspect the binding
kubectl describe pvc static-pvc
# Look for: Volume = local-pv

# Cleanup
kubectl delete -f 04-pvc-static.yaml
kubectl delete -f 03-pv-hostpath.yaml
```

**Lesson:** Static provisioning = admin creates PV, dev creates PVC, Kubernetes binds them.

### Experiment 4: Dynamic PVC (Automatic PV)

```powershell
# Just create a PVC — no PV needed!
kubectl apply -f 05-pvc-dynamic.yaml

# Check — a PV was AUTO-CREATED!
kubectl get pv,pvc
# PVC: STATUS = Bound
# PV:  A new PV appeared with a random name like pvc-xxxxxxxx

# Inspect
kubectl describe pvc dynamic-pvc

# Cleanup
kubectl delete -f 05-pvc-dynamic.yaml
# The auto-created PV is also deleted (Delete reclaim policy)
kubectl get pv   # ← PV is gone too!
```

**Lesson:** Dynamic provisioning = just create a PVC, Kubernetes handles the rest via StorageClass.

### Experiment 5: Full App with Persistence

```powershell
# Deploy PVC + App + Service
kubectl apply -f 05-pvc-dynamic.yaml
kubectl apply -f 06-deployment-storage.yaml
kubectl apply -f 07-service.yaml

# Wait for pod
kubectl get pods -l app=storage-demo -w

# Test at http://localhost:30081

# Cleanup
kubectl delete -f 07-service.yaml
kubectl delete -f 06-deployment-storage.yaml
kubectl delete -f 05-pvc-dynamic.yaml
```

---

## Troubleshooting

### PVC stuck in "Pending"

```powershell
kubectl describe pvc <pvc-name>
# Look at Events section for the reason
```

Common causes:
- **No default StorageClass** → `kubectl get sc` to check
- **storageClassName mismatch** → PVC class must match PV class (static) or a valid SC (dynamic)
- **Capacity issue** → PV size must be >= PVC request

### Pod stuck in "Pending" or "ContainerCreating"

```powershell
kubectl describe pod <pod-name>
# Look for "FailedMount" or "FailedScheduling" events
```

Common causes:
- PVC not bound yet
- Wrong `claimName` in pod spec
- RWO volume mounted on a different node

### Image pull error "ErrImagePull"

```powershell
# Make sure the image was built locally
docker images | Select-String "storage-demo"

# If using minikube, build inside minikube's Docker:
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -t storage-demo-app:v1 L4_Storage/app/
```

### Port 30081 not accessible

```powershell
# Check the service
kubectl get svc storage-demo-service

# For minikube, use:
minikube service storage-demo-service --url
```

---

## Quick Reference Commands

```powershell
# ── Storage Resources ──
kubectl get pv                    # List PersistentVolumes
kubectl get pvc                   # List PersistentVolumeClaims
kubectl get sc                    # List StorageClasses

# ── Detailed Info ──
kubectl describe pv <name>
kubectl describe pvc <name>
kubectl describe sc <name>

# ── Inside the Pod ──
kubectl exec -it <pod> -- ls -la /app/data
kubectl exec -it <pod> -- df -h /app/data
kubectl exec -it <pod> -- cat /app/data/<file>

# ── Debugging ──
kubectl get events --sort-by='.lastTimestamp'
kubectl describe pod <pod-name> | Select-String -Context 0,10 "Events"
```
