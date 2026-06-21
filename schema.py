from pydantic import BaseModel, Field
from typing import List,Literal,Optional

NodeTypes=Literal[
    "HydraulicProject",#水利项目
    "WaterSystem",#水系/流域    
    "Location",#地点
    "Organization", #机构
    "Technology", #水利技术
    "Equipment", #设备设施
    "Function" #功能
    ]

RelationType = Literal[
    "LOCATED_IN",       # HydraulicProject -> Location（位于某地）
    "ON_RIVER",         # HydraulicProject -> WaterSystem（建在某条河上）
    "PART_OF",          # HydraulicProject -> HydraulicProject（子工程属于母工程）
    "HAS_FUNCTION",     # HydraulicProject -> Function（工程的功能）
    "HAS_EQUIPMENT",    # HydraulicProject -> Equipment（工程的设备）
    "USES_TECH",        # HydraulicProject -> Technology（工程使用的技术）
    "SUPPLIES",         # HydraulicProject -> Location（向某地供水/供电）
    "PROTECTS",         # HydraulicProject -> Location（保护某地）
    "JOINT_DISPATCH",   # HydraulicProject -> HydraulicProject（联合调度）
    "FLOWS_THROUGH",    # WaterSystem -> Location（水系流经某地）
    "TRIBUTARY_OF",     # WaterSystem -> WaterSystem（支流）
    "MANAGES",          # Organization -> HydraulicProject（管理）
    "OPERATES",         # Organization -> HydraulicProject（运营）
    "SUBORDINATE_TO",   # Organization -> Organization（隶属）
]


class Node(BaseModel):
    type:NodeTypes=Field(description="节点类型（归一化）")
    name:str=Field(description="节点名称")
    aliases:Optional[List[str]]=Field(default_factory=list,description="节点别名")
    description:Optional[str]=Field(default=None,description="节点描述")

class Relationship(BaseModel):
    type:RelationType=Field(description="关系类型")
    source:str=Field(description="关系源节点")
    target:str=Field(description="关系目标节点")
    description:Optional[str]=Field(default=None,description="关系描述")

class Graph(BaseModel):
    nodes:List[Node]=Field(default_factory=list,description="节点列表")
    relationships:List[Relationship]=Field(default_factory=list,description="关系列表")

NodeTypes_Description={
    "HydraulicProject":"水利项目",
    "WaterSystem":"水系/流域",
    "Location":"地点",
    "Organization":"机构",
    "Technology":"水利技术",
    "Equipment":"设备设施",
    "Function":"功能",
    }

RelationTypes_Description={
    "LOCATED_IN":"位于某地（项目等为起点，省份城市等地点为终点）",
    "ON_RIVER":"建在某条河上（项目为起点，水系为终点）",
    "PART_OF":"子工程属于母工程（子项目为起点，母项目为终点）（通常隐含子工程的地点与水系与母工程相同）",
    "HAS_FUNCTION":"工程的功能（项目等为起点，功能为终点）",
    "HAS_EQUIPMENT":"工程的设备（项目等为起点，设备为终点）",
    "USES_TECH":"工程使用的技术（项目等为起点，技术为终点）",
    "SUPPLIES":"向某地供水/供电（项目等为起点，地点为终点）",
    "PROTECTS":"保护某地（项目等为起点，地点为终点）",
    "JOINT_DISPATCH":"联合调度",
    "FLOWS_THROUGH":"水系流经某地（水系为起点，地点为终点）",
    "TRIBUTARY_OF":"支流（子水系为起点，母水系为终点）",
    "MANAGES":"管理/负责（机构为起点，项目为终点）",
    "OPERATES":"运营（机构为起点，项目为终点）",
    "SUBORDINATE_TO":"隶属",
    }

