from pydantic import BaseModel, Field
from typing import List, Literal, Optional

# ===== 节点类型 =====
NodeTypes = Literal[
    "Project",       # 水利工程项目
    "WaterSystem",   # 自然水系/流域
    "Location",      # 行政地点
    "Organization",  # 机构
    "Technology",    # 技术
    "Function",      # 功能
]

# ===== 关系类型 =====
RelationType = Literal[
    "LOCATED_IN",       # Project/WaterSystem -> Location（位于）
    "ON_RIVER",         # Project -> WaterSystem（建在某河上）
    "FLOWS_THROUGH",    # WaterSystem -> Location（流经）
    "TRIBUTARY_OF",     # WaterSystem -> WaterSystem（支流）
    "PART_OF",          # Project -> Project（子工程属于母工程）
    "HAS_FUNCTION",     # Project -> Function
    "USES_TECH",        # Project -> Technology
    "MANAGES",          # Organization -> Project（管理/运营）
    "SUBORDINATE_TO",   # Organization -> Organization（隶属）
    "SUPPLIES",         # Project -> Location（供水/供电）
    "PROTECTS",         # Project -> Location（防洪保护）
    "JOINT_DISPATCH",   # Project -> Project（联合调度）
]


class Node(BaseModel):
    type: NodeTypes = Field(description="节点类型（归一化）")
    name: str = Field(description="节点名称")
    aliases: Optional[List[str]] = Field(default_factory=list, description="节点别名")
    description: Optional[str] = Field(default=None, description="节点描述")


class Relationship(BaseModel):
    type: RelationType = Field(description="关系类型")
    source: str = Field(description="关系源节点")
    target: str = Field(description="关系目标节点")
    description: Optional[str] = Field(default=None, description="关系描述")


class Graph(BaseModel):
    nodes: List[Node] = Field(default_factory=list, description="节点列表")
    relationships: List[Relationship] = Field(default_factory=list, description="关系列表")


# ===== 节点类型说明（精简版）=====
NodeTypes_Description = {
    "Project":      "水利工程项目（含水库、枢纽、电站、调水/防洪工程等人工建设）。例：三峡工程、小浪底、南水北调中线",
    "WaterSystem":  "天然水系（河、湖、流域）。例：长江、淮河、黄河流域。⚠️人工水库归 Project",
    "Location":     "行政地点（省/市/县/区）。例：湖北省、宜昌市、华北平原",
    "Organization": "机构（部委、委员会、公司）。例：水利部、长江水利委员会、三峡集团",
    "Technology":   "技术/方法/工艺（无形）。例：碾压混凝土坝、灌浆技术。⚠️实物装置不在此",
    "Function":     "功能/作用（做什么）。例：防洪、发电、灌溉、供水。⚠️'发电'是Function，'水电技术'是Technology",
}


# ===== 关系类型说明（精简版）=====
RelationTypes_Description = {
    "LOCATED_IN":      "位于（Project/WaterSystem → Location）",
    "ON_RIVER":        "建在某河上（Project → WaterSystem）",
    "FLOWS_THROUGH":   "流经（WaterSystem → Location）",
    "TRIBUTARY_OF":    "支流（子水系 → 母水系）",
    "PART_OF":         "子工程隶属（子Project → 母Project）（通常子母工程的管理机构关系是一致的）",
    "HAS_FUNCTION":    "功能（Project → Function）",
    "USES_TECH":       "使用技术（Project → Technology）",
    "MANAGES":         "管理/运营（Organization → Project）",
    "SUBORDINATE_TO":  "机构隶属（下级Org → 上级Org）",
    "SUPPLIES":        "供水/供电（Project → Location）",
    "PROTECTS":        "保护（Project → Location）",
    "JOINT_DISPATCH":  "联合调度（Project ↔ Project）",
}
