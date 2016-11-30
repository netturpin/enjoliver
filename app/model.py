from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Machine(Base):
    __tablename__ = 'machine'
    uuid = Column(String, primary_key=True, autoincrement=False)

    interfaces = relationship("MachineInterface", lazy="joined")

    def __repr__(self):
        return "<%s: %s>" % (Machine.__name__, self.uuid)


class MachineInterface(Base):
    __tablename__ = 'machine-interface'

    mac = Column(String, nullable=False, primary_key=True, autoincrement=False)
    name = Column(String, nullable=False)
    netmask = Column(Integer, nullable=False)
    ipv4 = Column(String, nullable=False)
    cidrv4 = Column(String, nullable=False)
    as_boot = Column(Boolean, default=False)

    machine_uuid = Column(Integer, ForeignKey('machine.uuid'))
    chassis_port = relationship("ChassisPort")

    def __repr__(self):
        return "<%s: %s %s>" % (MachineInterface.__name__, self.mac, self.cidrv4)


class Chassis(Base):
    __tablename__ = 'chassis'

    name = Column(String, nullable=False)
    mac = Column(String, nullable=False, primary_key=True)

    ports = relationship("ChassisPort", lazy="joined")

    def __repr__(self):
        return "<%s: %s %s>" % (Chassis.__name__, self.mac, self.name)


class ChassisPort(Base):
    __tablename__ = 'chassis-port'

    mac = Column(String, primary_key=True, autoincrement=False)
    chassis_mac = Column(String, ForeignKey('chassis.mac'))

    machine_interface_mac = Column(String, ForeignKey('machine-interface.mac'))

    def __repr__(self):
        return "<%s: %s %s>" % (ChassisPort.__name__, self.mac, self.chassis_mac)


def insert_data(session, discovery):
    machine = Machine(
        uuid=discovery["boot-info"]["uuid"]
    )
    if len(session.query(Machine).filter(Machine.uuid == machine.uuid).all()) != 0:
        return False

    session.add(machine)
    interfaces = []
    for i in discovery["interfaces"]:
        if i["mac"]:
            interfaces.append(
                MachineInterface(
                    name=i["name"],
                    netmask=i["netmask"],
                    mac=i["mac"],
                    ipv4=i["ipv4"],
                    cidrv4=i["cidrv4"],
                    as_boot=True if i["mac"] == discovery["boot-info"]["mac"] else False,
                    machine_uuid=machine.uuid)
            )
    session.add_all(interfaces)
    for j in discovery["lldp"]["data"]["interfaces"]:
        chassis = Chassis(
            name=j["chassis"]["name"],
            mac=j["chassis"]["id"]
        )
        session.add(chassis)
        for machine_interface in interfaces:
            if machine_interface.name == j["name"]:
                ports = ChassisPort(
                    mac=j["port"]["id"],
                    chassis_mac=chassis.mac,
                    machine_interface_mac=machine_interface.mac
                )
                session.add(ports)

    session.commit()
    return True
