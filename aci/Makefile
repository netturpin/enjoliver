CWD=$(shell pwd)

ACI_DIR=$(CWD)

CORE := cni etcd fleet hyperkube lldp rkt vault iproute2 ceph-tools dnsmasq haproxy socat
KUBE := tiller heapster node-exporter kube-state-metrics prometheus
EXTRA := kube-dashboard vault-ui

.PHONY: default extra core kube

default: extra

core: $(CORE)

kube: $(KUBE)
kube_deps: core $(KUBE)
kube_deps_only: $(KUBE)

extra: $(EXTRA)
extra_deps: kube_deps $(EXTRA)

$(EXTRA)\
$(CORE)\
$(KUBE):
	IMAGE=aci-$@ $(MAKE) -C aci-$@
	IMAGE=aci-$@ $(MAKE) -C aci-$@ clean
