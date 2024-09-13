# Step 1: Prepare Kubernetes Servers

The minimal server requirements for the servers used in the cluster are:

2 GB or more of RAM per machine – any less leaves little room for your apps.
At least 2 CPUs on the machine that you use as a control-plane node.
Full network connectivity among all machines in the cluster – Can be private or public
Since this setup is meant for development purposes, I have setup the servers as mentioned below.

Server Type	Server Hostname	Specs

Master	k8s-master	4GB RAM, 2 vCPUs
Worker	k8s-worker01	4GB RAM, 2 vCPUs
Worker	k8s-worker02	4GB RAM, 2 vCPUs

# Login to all servers and update the OS.

> sudo yum -y update && sudo systemctl reboot

> Step 2: Install kubelet, kubeadm and kubectl

```
Once the servers are rebooted, add Kubernetes repository for CentOS 7 to all the servers.
```
# Add Kubernetes repository

> sudo tee /etc/yum.repos.d/kubernetes.repo<<EOF
>[kubernetes]
>name=Kubernetes
>baseurl=https://packages.cloud.google.com/yum/repos/kubernetes-el7-x86_64
>enabled=1
>gpgcheck=1
>repo_gpgcheck=0
>gpgkey=https://packages.cloud.google.com/yum/doc/yum-key.gpg https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
>EOF

# Then install required packages.

>sudo yum clean all && sudo yum -y makecache

>sudo yum -y install epel-release vim git curl wget kubelet kubeadm kubectl --disableexcludes=kubernetes


# Confirm installation by checking the version of kubeadm and kubectl.

>kubeadm  version

>kubeadm version: &version.Info{Major:"1", Minor:"22", GitVersion:"v1.22.2", GitCommit:"8b5a19147530eaac9476b0ab82980b4088bbc1b2", GitTreeState:"clean", BuildDate:"2021-09-15T21:37:34Z", GoVersion:"go1.16.8", Compiler:"gc", Platform:"linux/amd64"}
 
>kubectl version --client
```
Client Version: version.Info{Major:"1", Minor:"22", GitVersion:"v1.22.2", GitCommit:"8b5a19147530eaac9476b0ab82980b4088bbc1b2", GitTreeState:"clean", BuildDate:"2021-09-15T21:38:50Z", GoVersion:"go1.16.8", Compiler:"gc", Platform:"linux/amd64"}
```

# Step 3: Disable SELinux and Swap


# If you have SELinux in enforcing mode, turn it off or use Permissive mode.

> sudo setenforce 0
> sudo sed -i 's/^SELINUX=.*/SELINUX=permissive/g' /etc/selinux/config

# Turn off swap.
>sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
>sudo swapoff -a


# Configure sysctl.

>sudo modprobe overlay
>sudo modprobe br_netfilter
 
>sudo tee /etc/sysctl.d/kubernetes.conf<<EOF
>net.bridge.bridge-nf-call-ip6tables = 1
>net.bridge.bridge-nf-call-iptables = 1
>net.ipv4.ip_forward = 1
>EOF
 
>sudo sysctl --system

# Step 4: Install Container runtime
To run containers in Pods, Kubernetes uses a container runtime. Supported container runtimes are:

Docker
Containerd
NOTE: You have to choose one runtime at a time.

Using Docker Container runtime

When using Docker container engine run the commands below to install it:

# Install packages
> sudo yum install -y yum-utils device-mapper-persistent-data lvm2
> sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
> sudo yum install docker-ce docker-ce-cli containerd.io
 
# Create required directories
> sudo mkdir /etc/docker
> sudo mkdir -p /etc/systemd/system/docker.service.d
 
# Create daemon json config file
> sudo tee /etc/docker/daemon.json <<EOF
> {
>  "exec-opts": ["native.cgroupdriver=systemd"],
>  "log-driver": "json-file",
>  "log-opts": {
>    "max-size": "100m"
>  },
>  "storage-driver": "overlay2",
>  "storage-opts": [
>    "overlay2.override_kernel_check=true"
>  ]
>}
>EOF
 
# Start and enable Services
>sudo systemctl daemon-reload
>sudo systemctl restart docker
>sudo systemctl enable docker

# Using Containerd


Below are the installation steps for Containerd.

# Configure containerd and start service
>sudo mkdir -p /etc/containerd
>sudo containerd config default > /etc/containerd/config.toml
 
# restart containerd
>sudo systemctl restart containerd
>sudo systemctl enable containerd

# Step 5: Configure Firewalld
# recommend you disable firewalld on your nodes:
> sudo systemctl disable --now firewalld

If you have an active firewalld service there are a number of ports to be enabled.

```
Master Server ports:
sudo firewall-cmd --add-port={6443,2379-2380,10250,10251,10252,5473,179,5473}/tcp --permanent
sudo firewall-cmd --add-port={4789,8285,8472}/udp --permanent
sudo firewall-cmd --reload
Worker Node ports:
sudo firewall-cmd --add-port={10250,30000-32767,5473,179,5473}/tcp --permanent
sudo firewall-cmd --add-port={4789,8285,8472}/udp --permanent
sudo firewall-cmd --reload
```
# Step 6: Initialize your control-plane node

# Enable and Start kubelet service.
> sudo systemctl enable kubelet (Do not start in node)
> sudo systemctl start kubelet (Do not start in node)

```
Create cluster:
sudo kubeadm init \
  --pod-network-cidr=10.244.0.0/16
Configure kubectl using commands in the output:
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
Check cluster status:
kubectl cluster-info
kubectl get nodes -owide
Step 7: Add worker nodes
With the control plane ready you can add worker nodes to the cluster for running scheduled workloads.

The join command that was given is used to add a worker node to the cluster.

kubeadm join k8s-cluster:6443 \
  --token zoy8cq.6v349sx9ass8dzyj \
  --discovery-token-ca-cert-hash sha256:14a6e33ca8dc9998f984150bc8780ddf0c3ff9cf6a3848f49825e53ef1374e24

Once node setup done Then apply below command on master:

kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
```