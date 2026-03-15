<template>
  <aside class="side">
    <div class="logo-wrap">
      <div class="logo">A</div>
      <div>
        <div class="name">Agent Review</div>
        <div class="sub">{{ uiText.systemName }}</div>
      </div>
    </div>
    <el-menu :default-active="$route.path" :default-openeds="['knowledge-group']" router class="menu">
      <el-menu-item index="/dashboard">
        <i class="el-icon-data-analysis"></i>
        <span>{{ uiText.dashboard }}</span>
      </el-menu-item>

      <el-submenu index="knowledge-group">
        <template slot="title">
          <i class="el-icon-collection"></i>
          <span>{{ uiText.knowledge }}</span>
        </template>
        <el-menu-item v-for="item in knowledgeMenus" :key="item.path" :index="item.path">
          {{ item.label }}
        </el-menu-item>
      </el-submenu>

      <el-menu-item index="/pre-review">
        <i class="el-icon-document-checked"></i>
        <span>{{ uiText.preReview }}</span>
      </el-menu-item>
    </el-menu>
  </aside>
</template>

<script>
export default {
  name: "AppSidebar",
  data() {
    return {
      uiText: {
        systemName: "药审预审系统",
        dashboard: "仪表盘",
        knowledge: "知识库",
        preReview: "预审项目",
      },
      knowledgeMenus: [
        { path: "/knowledge/guideline", label: "指导原则" },
        { path: "/knowledge/policy", label: "制度规范" },
        { path: "/knowledge/law", label: "法律法规" },
        { path: "/knowledge/pharmacopeia", label: "药典数据" },
        { path: "/knowledge/experience", label: "历史经验" },
        { path: "/knowledge/common-issue", label: "共性问题" },
        { path: "/knowledge/review-rule", label: "审评规则" },
      ],
    };
  },
};
</script>

<style scoped>
.side {
  width: 240px;
  height: 100%;
  background: linear-gradient(180deg, #f8fbff 0%, #eef3fa 100%);
  color: #2f3b4a;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #dbe5f0;
}

.logo-wrap {
  height: 68px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid #e3ebf5;
}

.logo {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4fc3f7, #1565c0);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
}

.name {
  font-size: 14px;
  color: #1f2d3d;
  font-weight: 700;
}

.sub {
  font-size: 12px;
  color: #5f6f81;
}

.menu {
  border-right: 0;
  background: transparent;
  padding: 10px 8px;
}

.menu .el-menu-item,
.menu /deep/ .el-submenu__title {
  color: #2f3b4a;
  border-radius: 8px;
  margin-bottom: 4px;
}

.menu .el-menu-item.is-active {
  background: #dfefff;
  color: #1f5fae;
  font-weight: 600;
}

.menu .el-menu-item:hover,
.menu /deep/ .el-submenu__title:hover {
  background: #eaf3ff;
}

.menu /deep/ .el-submenu .el-menu-item {
  min-width: 0;
}
</style>
