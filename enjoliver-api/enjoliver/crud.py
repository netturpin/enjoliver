"""
Over the application Model, queries to the database
"""

import datetime
import logging

from sqlalchemy.orm import sessionmaker, Session, joinedload

from enjoliver.db import session_commit
from enjoliver import tools
from enjoliver.model import MachineInterface, Machine, Schedule, ScheduleRoles, LifecycleIgnition, \
    LifecycleCoreosInstall, LifecycleRolling

logger = logging.getLogger(__name__)


class InjectLifecycle:
    """
    Store the data from the Lifecycle machine state
    """

    def __init__(self, session, request_raw_query):
        self.session = session
        self.adds = 0
        self.updates = 0

        self.mac = tools.get_mac_from_raw_query(request_raw_query)

        self.machine = self.session.query(Machine).join(MachineInterface).filter(
            MachineInterface.mac == self.mac).first()
        if not self.machine:
            m = "InjectLifecycle mac: '%s' unknown in db" % self.mac
            logger.error(m)
            raise AttributeError(m)
        logger.debug("InjectLifecycle mac: %s" % self.mac)

    def refresh_lifecycle_ignition(self, up_to_date: bool):
        lifecycle = self.session.query(LifecycleIgnition).filter(
            LifecycleIgnition.machine_id == self.machine.id).first()
        if not lifecycle:
            lifecycle = LifecycleIgnition(
                machine_id=self.machine.id,
                up_to_date=up_to_date
            )
            self.session.add(lifecycle)
        else:
            now = datetime.datetime.utcnow()
            if lifecycle.up_to_date != up_to_date:
                lifecycle.last_change_date = now
            lifecycle.up_to_date = up_to_date
            lifecycle.updated_date = now

        self.session.commit()

    def refresh_lifecycle_coreos_install(self, success: bool):
        lifecycle = self.session.query(LifecycleCoreosInstall).filter(
            LifecycleCoreosInstall.machine_id == self.machine.id).first()
        if not lifecycle:
            lifecycle = LifecycleCoreosInstall(
                machine_id=self.machine.id,
                success=success
            )
            self.session.add(lifecycle)
        else:
            lifecycle.up_to_date = success
            lifecycle.updated_date = datetime.datetime.utcnow()

        self.session.commit()

    def apply_lifecycle_rolling(self, enable: bool, strategy="kexec"):
        lifecycle = self.session.query(LifecycleRolling).filter(
            LifecycleRolling.machine_id == self.machine.id).first()
        if not lifecycle:
            lifecycle = LifecycleRolling(
                machine_id=self.machine.id,
                enable=enable,
                strategy=strategy,
            )
            self.session.add(lifecycle)
        else:
            lifecycle.enable = enable
            lifecycle.strategy = strategy
            lifecycle.updated_date = datetime.datetime.utcnow()

        self.session.commit()


class FetchLifecycle:
    """
    Get the data of the Lifecycle state
    """

    def __init__(self, sess_maker: sessionmaker):
        self.sess_maker = sess_maker

    def get_ignition_uptodate_status(self, mac: str):
        with session_commit(sess_maker=self.sess_maker) as session:
            lf = session.query(LifecycleIgnition)\
                .join(Machine)\
                .join(MachineInterface)\
                .filter(MachineInterface.mac == mac)\
                .first()
            if lf:
                return lf.up_to_date
            else:
                return None

    def get_all_updated_status(self):
        status = []
        with session_commit(sess_maker=self.sess_maker) as session:
            for machine in session.query(Machine)\
                    .join(LifecycleIgnition)\
                    .join(MachineInterface)\
                    .filter(MachineInterface.as_boot == True):

                status.append({
                    "up-to-date": machine.lifecycle_ignition[0].up_to_date,
                    "fqdn": machine.interfaces[0].fqdn,
                    "mac": machine.interfaces[0].mac,
                    "cidrv4": machine.interfaces[0].cidrv4,
                    "created_date": machine.created_date,
                    "updated_date": machine.updated_date,
                    "last_change_date": machine.lifecycle_ignition[0].last_change_date,
                })
        return status

    def get_coreos_install_status(self, mac: str):
        with session_commit(sess_maker=self.sess_maker) as session:
            lci = session.query(LifecycleCoreosInstall)\
                .join(Machine)\
                .join(MachineInterface)\
                .filter(MachineInterface.mac == mac)\
                .first()
            if lci:
                return lci.success
            else:
                return None

    def get_all_coreos_install_status(self):
        life_status_list = []
        with session_commit(sess_maker=self.sess_maker) as session:
            for machine in session.query(Machine)\
                    .join(LifecycleCoreosInstall)\
                    .join(MachineInterface)\
                    .filter(MachineInterface.as_boot == True):

                life_status_list.append({
                    "mac": machine.interfaces[0].mac,
                    "fqdn": machine.interfaces[0].fqdn,
                    "cidrv4": machine.interfaces[0].cidrv4,
                    "success": machine.lifecycle_coreos_install[0].success,
                    "created_date": machine.lifecycle_coreos_install[0].created_date,
                    "updated_date": machine.lifecycle_coreos_install[0].updated_date
                })
        return life_status_list

    def get_rolling_status(self, mac: str):
        with session_commit(sess_maker=self.sess_maker) as session:
            for m in session.query(Machine)\
                    .join(MachineInterface)\
                    .filter(MachineInterface.mac == mac)\
                    .join(LifecycleRolling):
                try:
                    rolling = m.lifecycle_rolling[0]
                    return rolling.enable, rolling.strategy
                except IndexError:
                    pass

            logger.debug("mac: %s return None" % mac)
            return None, None

    def get_all_rolling_status(self):
        life_roll_list = []
        with session_commit(sess_maker=self.sess_maker) as session:
            for machine in session.query(Machine) \
                    .join(LifecycleRolling) \
                    .join(MachineInterface) \
                    .options(joinedload("interfaces")) \
                    .options(joinedload("lifecycle_rolling")) \
                    .filter(MachineInterface.as_boot == True):
                try:
                    life_roll_list.append({
                        "mac": machine.interfaces[0].mac,
                        "fqdn": machine.interfaces[0].fqdn,
                        "cidrv4": machine.interfaces[0].cidrv4,
                        "enable": bool(machine.lifecycle_rolling[0].enable),
                        "created_date": machine.lifecycle_rolling[0].created_date,
                        "updated_date": machine.lifecycle_rolling[0].updated_date
                    })
                except IndexError:
                    pass
        return life_roll_list


class BackupExport:
    def __init__(self, sess_maker: sessionmaker):
        self.sess_maker = sess_maker

    @staticmethod
    def _construct_discovery(machine: Machine):
        interfaces = list()
        mac_boot = ""
        for interface in machine.interfaces:
            if interface.as_boot is True:
                mac_boot = interface.mac
            interfaces.append({
                'mac': interface.mac,
                'netmask': interface.netmask,
                'ipv4': interface.ipv4,
                'cidrv4': interface.ipv4,
                'name': interface.name,
                "gateway": interface.gateway,
                "fqdn": [interface.fqdn]
            })
        if mac_boot == "":
            raise LookupError("fail to retrieve mac boot in %s" % interfaces)

        return {
            "boot-info": {
                "uuid": machine.uuid,
                "mac": mac_boot,
                "random-id": "",
            },

            "interfaces": interfaces,
            "disks": [{
                'size-bytes': k.size,
                'path': k.path
            } for k in machine.disks],

            # TODO LLDP
            "lldp": {
                'data': {'interfaces': None},
                'is_file': False
            },

            "ignition-journal": None
        }

    @staticmethod
    def _construct_schedule(mac: str, schedule_type: str):
        """
        Construct the schedule as the scheduler does
        :param mac:
        :param schedule_type:
        :return: dict
        """
        # TODO maybe decide to drop etcd-member because it's tricky to deal with two roles
        # etcd-member + kubernetes-control-plane: in fact it's only one
        if schedule_type == ScheduleRoles.kubernetes_control_plane:
            roles = [ScheduleRoles.kubernetes_control_plane, ScheduleRoles.etcd_member]
        else:
            roles = [ScheduleRoles.kubernetes_node]
        return {
            u"roles": roles,
            u'selector': {
                u"mac": mac
            }
        }

    def get_playbook(self):
        """
        Get and reproduce the data sent inside the db from an API level
        :return:
        """
        playbook = []
        with session_commit(sess_maker=self.sess_maker) as session:
            for schedule_type in [ScheduleRoles.kubernetes_control_plane, ScheduleRoles.kubernetes_node]:
                for machine in session.query(Machine).filter(Machine.schedules.any(Schedule.role == schedule_type)):
                    discovery_data = self._construct_discovery(machine)
                    schedule_data = self._construct_schedule(discovery_data["boot-info"]["mac"], schedule_type)
                    playbook.append({"data": discovery_data, "route": "/discovery"})
                    playbook.append({"data": schedule_data, "route": "/scheduler"})

        return playbook
