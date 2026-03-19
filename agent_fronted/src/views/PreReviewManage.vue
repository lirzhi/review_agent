<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <h2 class="page-title">预审项目管理</h2>
        <div class="page-desc">创建预审项目，维护注册分类信息，进入项目会话后再按专业类别上传申报资料。</div>
      </div>
      <div>
        <el-button type="primary" @click="openCreateDialog">创建预审项目</el-button>
      </div>
    </div>

    <el-card class="k-card">
      <div slot="header">项目列表</div>
      <el-table :data="projects" border class="k-table compact-table">
        <el-table-column prop="project_id" label="项目 ID" min-width="180" />
        <el-table-column prop="project_name" label="项目名称" min-width="180" />
        <el-table-column prop="registration_scope" label="注册大类" width="100" />
        <el-table-column prop="registration_leaf" label="注册分类" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="version_count" label="版本数" width="80" />
        <el-table-column prop="current_version" label="当前版本" width="90" />
        <el-table-column prop="create_time" label="创建时间" width="165" />
        <el-table-column prop="update_time" label="更新时间" width="180" />
        <el-table-column label="操作" width="220">
          <template slot-scope="scope">
            <el-button type="text" @click="openSession(scope.row)">查看当前版本</el-button>
            <el-button type="text" @click="viewRuns(scope.row)">查看历史版本</el-button>
            <el-button type="text" style="color: #c62828" @click="dropProject(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="selectedProject.project_id" class="k-card">
      <div slot="header">运行记录 - {{ selectedProject.project_name }}</div>
      <el-table :data="runs" border class="k-table">
        <el-table-column prop="run_id" label="Run ID" min-width="190" />
        <el-table-column prop="version_no" label="版本" width="90" />
        <el-table-column prop="source_file_name" label="申报资料" min-width="220" />
        <el-table-column prop="accuracy" label="准确率" width="100" />
        <el-table-column prop="feedback_count" label="反馈数" width="90" />
        <el-table-column prop="create_time" label="开始时间" width="170" />
        <el-table-column prop="finish_time" label="结束时间" width="170" />
        <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-dialog title="创建预审项目" :visible.sync="createDialog.visible" width="760px">
      <el-form label-width="110px" size="small">
        <el-form-item label="项目名称">
          <el-input v-model="projectForm.project_name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="projectForm.owner" placeholder="请输入负责人" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="projectForm.description" type="textarea" :rows="3" placeholder="请输入项目描述" />
        </el-form-item>
        <el-form-item label="注册大类">
          <el-select v-model="projectForm.registration_scope" placeholder="请选择注册大类" style="width: 100%" @change="onRegistrationScopeChange">
            <el-option v-for="item in registrationScopeOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="注册分类路径">
          <el-cascader
            v-model="projectForm.registration_path"
            :options="registrationOptions"
            :props="registrationCascaderProps"
            clearable
            filterable
            style="width: 100%"
            placeholder="请选择注册分类"
            @change="onRegistrationPathChange"
          />
        </el-form-item>
        <el-form-item label="分类说明">
          <div class="registration-panel" v-if="registrationDescriptions.length">
            <div v-for="(item, index) in registrationDescriptions" :key="`${item.label}-${index}`" class="registration-item">
              <div class="registration-title">{{ item.label }}</div>
              <div class="registration-desc">{{ item.description }}</div>
            </div>
          </div>
          <div v-else class="empty-tip">选择注册分类后，这里会展示各层级说明。</div>
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button @click="closeCreateDialog">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createProjectOnly">确认创建</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import { createProject, deleteProject, listProjects, runHistory } from "@/api/prereview";
import { PRE_REVIEW_REGISTRATION_OPTIONS, findRegistrationNodes } from "@/constants/registration";

export default {
  name: "PreReviewManage",
  data() {
    return {
      projectForm: this.getDefaultProjectForm(),
      projects: [],
      selectedProject: { project_id: "", project_name: "" },
      runs: [],
      creating: false,
      createDialog: { visible: false },
      registrationCascaderProps: {
        value: "value",
        label: "label",
        children: "children",
        emitPath: true,
        checkStrictly: false,
      },
    };
  },
  computed: {
    registrationScopeOptions() {
      return PRE_REVIEW_REGISTRATION_OPTIONS.map((item) => item.value);
    },
    registrationOptions() {
      if (!this.projectForm.registration_scope) {
        return [];
      }
      return PRE_REVIEW_REGISTRATION_OPTIONS.filter((item) => item.value === this.projectForm.registration_scope);
    },
    registrationDescriptions() {
      return findRegistrationNodes(this.projectForm.registration_path).map((item) => ({
        label: item.label,
        description: item.description || "",
      }));
    },
  },
  mounted() {
    this.loadProjects();
  },
  methods: {
    getDefaultProjectForm() {
      return {
        project_name: "",
        owner: "",
        description: "",
        registration_scope: "",
        registration_path: [],
      };
    },
    async loadProjects() {
      try {
        const res = await listProjects({ page: 1, page_size: 100 });
        this.projects = (res.data && res.data.list) || [];
      } catch (_) {
        this.projects = [];
      }
    },
    openCreateDialog() {
      this.createDialog.visible = true;
    },
    closeCreateDialog() {
      this.createDialog.visible = false;
      this.projectForm = this.getDefaultProjectForm();
    },
    onRegistrationScopeChange() {
      this.projectForm.registration_path = this.projectForm.registration_scope ? [this.projectForm.registration_scope] : [];
    },
    onRegistrationPathChange(path) {
      if (!Array.isArray(path) || !path.length) {
        this.projectForm.registration_path = [];
        return;
      }
      this.projectForm.registration_scope = path[0] || "";
    },
    async createProjectOnly() {
      if (!this.projectForm.project_name) {
        this.$message.warning("请输入项目名称");
        return;
      }
      if (!this.projectForm.registration_scope) {
        this.$message.warning("请选择注册大类");
        return;
      }
      if (!this.projectForm.registration_path.length) {
        this.$message.warning("请选择注册分类路径");
        return;
      }
      this.creating = true;
      try {
        const nodes = findRegistrationNodes(this.projectForm.registration_path);
        const registrationLeaf = nodes.length ? nodes[nodes.length - 1].value : "";
        const registrationDescription = nodes
          .map((item) => `${item.label}：${item.description || ""}`)
          .join("\n\n");
        const payload = {
          project_name: this.projectForm.project_name,
          owner: this.projectForm.owner,
          description: this.projectForm.description,
          registration_scope: this.projectForm.registration_scope,
          registration_path: this.projectForm.registration_path,
          registration_leaf: registrationLeaf,
          registration_description: registrationDescription,
        };
        const res = await createProject(payload);
        const data = (res && res.data) || {};
        const projectId = data.project_id;
        if (!projectId) {
          throw new Error("项目创建成功但未返回 project_id");
        }
        this.$message.success((res && res.message) || "项目创建成功");
        this.closeCreateDialog();
        await this.loadProjects();
        this.$router.push({ name: "pre-review-session", params: { projectId } });
      } catch (e) {
        this.$message.error((e && e.message) || "创建项目失败");
      } finally {
        this.creating = false;
      }
    },
    async dropProject(row) {
      try {
        await this.$confirm(`确认删除项目 ${row.project_name} ?`, "提示", { type: "warning" });
        await deleteProject(row.project_id);
        this.$message.success("删除成功");
        if (this.selectedProject.project_id === row.project_id) {
          this.selectedProject = { project_id: "", project_name: "" };
          this.runs = [];
        }
        this.loadProjects();
      } catch (_) {}
    },
    openSession(row) {
      this.$router.push({ name: "pre-review-session", params: { projectId: row.project_id } });
    },
    async viewRuns(row) {
      this.selectedProject = { project_id: row.project_id, project_name: row.project_name };
      try {
        const res = await runHistory({ project_id: row.project_id });
        this.runs = res.data || [];
      } catch (_) {
        this.runs = [];
      }
    },
  },
};
</script>

<style scoped>
.registration-panel {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #f8fafc;
}

.registration-item + .registration-item {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #d1d5db;
}

.registration-title {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

.registration-desc,
.empty-tip {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: #4b5563;
}

.compact-table ::v-deep .cell {
  word-break: break-word;
}
</style>
