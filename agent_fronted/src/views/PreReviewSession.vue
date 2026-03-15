<template>
  <div class="session-page page-shell">
    <div class="page-header">
      <div>
        <h2 class="page-title">预审会话</h2>
        <div class="page-desc">项目：{{ project.project_name || projectId }}，上传申报资料并按章节生成预审结论</div>
      </div>
    </div>

    <el-row :gutter="16" class="fill-row">
      <el-col :span="9" class="fill-col">
        <el-card class="k-card full-height">
          <div slot="header" class="head-row">
            <span>申报资料原文</span>
            <el-select v-model="activeDocId" size="mini" filterable placeholder="选择资料" style="width: 280px" @change="onDocChange">
              <el-option v-for="x in submissions" :key="x.doc_id" :label="`${x.file_name} (${x.doc_id})`" :value="x.doc_id" />
            </el-select>
          </div>
          <div class="content-wrap">
            <template v-if="activeDocId">
              <object v-if="isPdfActive" :data="previewUrl" type="application/pdf" class="preview-frame">
                <pre class="origin-text">{{ submissionText || "浏览器不支持 PDF 预览，请下载后查看。" }}</pre>
              </object>
              <iframe v-else-if="isWordActive" :src="previewUrl" class="preview-frame" />
              <pre v-else class="origin-text">{{ submissionText || "请先选择资料查看原文" }}</pre>
            </template>
            <pre v-else class="origin-text">请先选择资料查看原文</pre>
          </div>
        </el-card>
      </el-col>

      <el-col :span="15" class="fill-col">
        <el-card class="k-card">
          <div slot="header">会话操作</div>
          <el-form :inline="true" size="small">
            <el-form-item>
              <el-upload action="#" :auto-upload="false" :show-file-list="false" :on-change="onPickSubmission">
                <el-button size="small">选择申报资料</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="small" :loading="uploading" @click="uploadSubmissionFile">上传资料</el-button>
            </el-form-item>
            <el-form-item>
              <el-button type="success" size="small" :loading="running" @click="run">执行预审</el-button>
            </el-form-item>
            <el-form-item>
              <el-button size="small" @click="loadSubmissions">刷新资料</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="submissions" border class="k-table" style="margin-top: 8px">
            <el-table-column prop="doc_id" label="Doc ID" min-width="170" />
            <el-table-column prop="file_name" label="文件名" min-width="220" />
            <el-table-column prop="file_type" label="类型" width="90" />
            <el-table-column prop="chunk_size" label="分块数" width="90" />
            <el-table-column prop="create_time" label="上传时间" width="170" />
            <el-table-column label="操作" width="120">
              <template slot-scope="s">
                <el-button type="text" @click="pickSubmission(s.row)">查看原文</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="k-card" style="margin-top: 16px">
          <div slot="header">预审结果</div>
          <el-table :data="runs" border class="k-table">
            <el-table-column prop="run_id" label="Run ID" min-width="170" />
            <el-table-column prop="version_no" label="版本" width="80" />
            <el-table-column prop="source_file_name" label="资料" min-width="180" />
            <el-table-column prop="summary" label="摘要" min-width="280" show-overflow-tooltip />
            <el-table-column prop="create_time" label="开始" width="160" />
            <el-table-column prop="finish_time" label="结束" width="160" />
            <el-table-column label="操作" width="120">
              <template slot-scope="s">
                <el-button type="text" @click="viewSections(s.row)">章节结论</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-table :data="sections" border class="k-table" style="margin-top: 12px">
            <el-table-column prop="section_name" label="章节" width="220" />
            <el-table-column prop="risk_level" label="风险" width="90" />
            <el-table-column prop="conclusion" label="结论" min-width="360" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import {
  listSubmissions,
  projectDetail,
  runHistory,
  runPreReview,
  sectionConclusions,
  submissionContent,
  submissionPreviewUrl,
  uploadSubmission,
} from "@/api/prereview";

export default {
  name: "PreReviewSession",
  data() {
    return {
      projectId: "",
      project: {},
      uploads: { file: null },
      uploading: false,
      running: false,
      submissions: [],
      activeDocId: "",
      activeFileType: "",
      submissionText: "",
      previewUrl: "",
      runs: [],
      sections: [],
    };
  },
  computed: {
    isPdfActive() {
      return this.activeFileType === "pdf";
    },
    isWordActive() {
      return this.activeFileType === "doc" || this.activeFileType === "docx";
    },
  },
  mounted() {
    this.projectId = this.$route.params.projectId || "";
    if (!this.projectId) {
      this.$message.error("缺少 projectId");
      return;
    }
    this.init();
  },
  methods: {
    async init() {
      await Promise.all([this.loadProject(), this.loadSubmissions(), this.loadRuns()]);
    },
    async loadProject() {
      try {
        const res = await projectDetail(this.projectId);
        this.project = res.data || {};
      } catch (_) {
        this.project = { project_id: this.projectId, project_name: this.projectId };
      }
    },
    onPickSubmission(file) {
      this.uploads.file = file && file.raw ? file.raw : null;
    },
    async uploadSubmissionFile() {
      if (!this.uploads.file) {
        this.$message.warning("请先选择申报资料文件");
        return;
      }
      this.uploading = true;
      try {
        const fd = new FormData();
        fd.append("file", this.uploads.file);
        const res = await uploadSubmission(this.projectId, fd);
        this.$message.success((res && res.message) || "上传成功");
        this.uploads.file = null;
        await this.loadSubmissions();
      } catch (e) {
        const msg = (e && e.response && e.response.data && e.response.data.message) || e.message || "上传失败";
        this.$message.error(msg);
      } finally {
        this.uploading = false;
      }
    },
    _syncActiveDocMeta() {
      const row = this.submissions.find((x) => x.doc_id === this.activeDocId);
      this.activeFileType = row ? String(row.file_type || "").toLowerCase() : "";
      this.previewUrl = this.activeDocId ? submissionPreviewUrl(this.projectId, this.activeDocId) : "";
    },
    async loadSubmissions() {
      try {
        const res = await listSubmissions(this.projectId, { page: 1, page_size: 200 });
        this.submissions = (res.data && res.data.list) || [];
        if (!this.activeDocId && this.submissions.length) {
          this.activeDocId = this.submissions[0].doc_id;
        }
        this._syncActiveDocMeta();
        if (this.activeDocId) {
          await this.loadSubmissionText();
        }
      } catch (_) {
        this.submissions = [];
      }
    },
    async onDocChange() {
      this._syncActiveDocMeta();
      await this.loadSubmissionText();
    },
    pickSubmission(row) {
      this.activeDocId = row.doc_id;
      this.onDocChange();
    },
    async loadSubmissionText() {
      if (!this.activeDocId) {
        this.submissionText = "";
        return;
      }
      try {
        const res = await submissionContent(this.projectId, this.activeDocId);
        this.submissionText = (res.data && res.data.content) || "";
      } catch (e) {
        this.submissionText = "";
        const msg = (e && e.response && e.response.data && e.response.data.message) || e.message || "加载原文失败";
        this.$message.error(msg);
      }
    },
    async run() {
      if (!this.activeDocId) {
        this.$message.warning("请先上传并选择申报资料");
        return;
      }
      this.running = true;
      try {
        const res = await runPreReview({ project_id: this.projectId, source_doc_id: this.activeDocId });
        this.$message.success((res && res.message) || "预审完成");
        await this.loadRuns();
      } catch (e) {
        const msg = (e && e.response && e.response.data && e.response.data.message) || e.message || "预审失败";
        this.$message.error(msg);
      } finally {
        this.running = false;
      }
    },
    async loadRuns() {
      try {
        const res = await runHistory({ project_id: this.projectId });
        this.runs = res.data || [];
      } catch (_) {
        this.runs = [];
      }
    },
    async viewSections(row) {
      try {
        const res = await sectionConclusions(row.run_id, {});
        this.sections = res.data || [];
      } catch (_) {
        this.sections = [];
      }
    },
  },
};
</script>

<style scoped>
.session-page {
  min-height: calc(100vh - 110px);
}

.fill-row,
.fill-col {
  height: 100%;
}

.full-height {
  height: calc(100vh - 142px);
}

.full-height /deep/ .el-card__body {
  height: calc(100% - 56px);
}

.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.content-wrap {
  height: 100%;
  overflow: auto;
}

.origin-text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.65;
  font-size: 13px;
}

.preview-frame {
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}
</style>
