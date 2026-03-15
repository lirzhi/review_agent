<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <h2 class="page-title">预审项目管理</h2>
        <div class="page-desc">创建项目、进入会话、查看历史版本与审计记录</div>
      </div>
      <div>
        <el-button type="primary" @click="openCreateDialog">创建预审项目</el-button>
      </div>
    </div>

    <el-card class="k-card">
      <div slot="header">项目列表</div>
      <el-table :data="projects" border class="k-table">
        <el-table-column prop="project_id" label="项目 ID" min-width="180" />
        <el-table-column prop="project_name" label="项目名称" min-width="180" />
        <el-table-column prop="owner" label="负责人" width="120" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="progress" label="进度" width="150">
          <template slot-scope="s">
            <el-progress :percentage="Math.round((s.row.progress || 0) * 100)" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column prop="update_time" label="更新时间" width="180" />
        <el-table-column label="操作" width="300" fixed="right">
          <template slot-scope="s">
            <el-button type="text" @click="openSession(s.row)">进入会话</el-button>
            <el-button type="text" @click="viewRuns(s.row)">运行记录</el-button>
            <el-button type="text" style="color: #c62828" @click="dropProject(s.row)">删除</el-button>
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

    <el-dialog title="创建预审项目并上传申报资料" :visible.sync="createDialog.visible" width="640px">
      <el-form label-width="90px" size="small">
        <el-form-item label="项目名称">
          <el-input v-model="projectForm.project_name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="projectForm.owner" placeholder="请输入负责人" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="projectForm.description" type="textarea" :rows="3" placeholder="请输入项目描述" />
        </el-form-item>
        <el-form-item label="申报资料">
          <el-upload
            action="#"
            :auto-upload="false"
            multiple
            :file-list="createDialog.files"
            :on-change="onSubmissionSelect"
            :on-remove="onSubmissionRemove"
            accept=".pdf,.doc,.docx,.txt,.md"
          >
            <el-button size="small">选择文件</el-button>
          </el-upload>
          <div class="upload-tip">支持多文件上传，创建项目后自动上传到该项目</div>
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button @click="closeCreateDialog">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createWithSubmission">确认创建并上传</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import { createProject, deleteProject, listProjects, runHistory, uploadSubmission } from "@/api/prereview";

export default {
  name: "PreReviewManage",
  data() {
    return {
      projectForm: { project_name: "", owner: "", description: "" },
      projects: [],
      selectedProject: { project_id: "", project_name: "" },
      runs: [],
      creating: false,
      createDialog: { visible: false, files: [] },
    };
  },
  mounted() {
    this.loadProjects();
  },
  methods: {
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
      this.projectForm = { project_name: "", owner: "", description: "" };
      this.createDialog.files = [];
    },
    onSubmissionSelect(file, fileList) {
      this.createDialog.files = fileList;
    },
    onSubmissionRemove(file, fileList) {
      this.createDialog.files = fileList;
    },
    async createWithSubmission() {
      if (!this.projectForm.project_name) {
        this.$message.warning("请输入项目名称");
        return;
      }
      if (!this.createDialog.files.length) {
        this.$message.warning("请至少上传一个申报资料文件");
        return;
      }
      this.creating = true;
      try {
        const res = await createProject(this.projectForm);
        const data = (res && res.data) || {};
        const projectId = data.project_id;
        if (!projectId) {
          throw new Error("项目创建成功但未返回 project_id");
        }

        let successCount = 0;
        let failCount = 0;
        for (const item of this.createDialog.files) {
          const raw = item && item.raw;
          if (!raw) continue;
          const fd = new FormData();
          fd.append("file", raw);
          try {
            await uploadSubmission(projectId, fd);
            successCount += 1;
          } catch (_) {
            failCount += 1;
          }
        }

        if (successCount > 0 && failCount === 0) {
          this.$message.success("项目创建并上传成功");
        } else if (successCount > 0 && failCount > 0) {
          this.$message.warning(`项目已创建，资料部分上传成功：成功 ${successCount}，失败 ${failCount}`);
        } else {
          this.$message.warning("项目已创建，但申报资料上传失败");
        }

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
.upload-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 6px;
}
</style>
