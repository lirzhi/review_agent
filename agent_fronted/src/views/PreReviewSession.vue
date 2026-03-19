
<template>
  <div class="session-page">
    <div class="page-header">
      <div>
        <h2>预审会话</h2>
        <div class="meta-row">
          <span>项目 ID：{{ project.project_id || "-" }}</span>
          <span>项目名称：{{ project.project_name || "-" }}</span>
          <span>注册大类：{{ project.registration_scope || "-" }}</span>
          <el-tooltip effect="dark" :content="project.registration_description || '暂无分类说明'" placement="bottom">
            <span class="clickable">注册分类：{{ project.registration_leaf || "-" }}</span>
          </el-tooltip>
        </div>
        <div class="meta-row">
          <span>反馈优化回路</span>
          <el-switch
            v-model="experimentConfig.enableFeedbackOptimize"
            active-text="开启"
            inactive-text="关闭"
          />
          <span>用于消融实验，决定本次运行后的反馈是否进入优化闭环</span>
        </div>
      </div>
      <div class="actions">
        <el-button type="primary" size="small" @click="openUploadDialog">上传申报资料</el-button>
        <el-button type="success" size="small" :loading="running" @click="run">开始预审</el-button>
        <el-button size="small" :loading="runningSection" :disabled="!activeDocId || !currentBrowseSectionId" @click="runCurrentSectionReview">审评当前章节</el-button>
      </div>
    </div>

    <el-card>
      <div slot="header" class="toolbar">
        <div class="actions">
          <el-radio-group v-model="viewFilters.domain" size="small" @change="onViewFilterChange">
            <el-radio-button label="药学">药学</el-radio-button>
            <el-radio-button label="临床">临床</el-radio-button>
            <el-radio-button label="非临床">非临床</el-radio-button>
          </el-radio-group>
          <el-radio-group v-if="showPharmacyBranchSelector" v-model="viewFilters.branch" size="small" @change="onViewFilterChange">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="3.2.S">原料药</el-radio-button>
            <el-radio-button label="3.2.P">制剂</el-radio-button>
          </el-radio-group>
        </div>
        <div class="actions">
          <el-select v-model="activeDocId" size="small" clearable filterable placeholder="选择当前浏览文件" style="width: 320px" @change="onDocChange">
            <el-option v-for="item in currentBrowseFiles" :key="item.doc_id" :label="item.file_name" :value="item.doc_id" />
          </el-select>
          <el-button size="mini" :disabled="!activeDocId" @click="openPreviewDialog">查看原文件</el-button>
          <el-button size="mini" @click="loadSubmissions">刷新文件</el-button>
          <el-button size="mini" @click="loadRuns">刷新运行</el-button>
        </div>
      </div>

      <div class="workspace">
        <div class="pane left">
          <div class="pane-head">
            <div>
              <div class="title">章节树</div>
              <div class="muted">{{ activeDocLabel }}</div>
            </div>
          </div>
          <el-tree
            v-if="leftTreeData.length"
            class="chapter-tree"
            :data="leftTreeData"
            node-key="section_id"
            :props="treeProps"
            :highlight-current="true"
            :default-expand-all="false"
            @node-click="onBrowseSectionSelect"
          />
          <div v-else class="empty">暂无章节目录。</div>
        </div>

        <div class="pane middle">
          <div class="pane-head">
            <div>
              <div class="title">章节原文</div>
              <div class="muted">{{ currentContentSectionLabel }}</div>
            </div>
            <div class="actions">
              <el-radio-group v-model="contentViewMode" size="mini" @change="syncEditorToCurrentSection()">
                <el-radio-button label="raw">原文</el-radio-button>
                <el-radio-button label="cleaned">Markdown</el-radio-button>
              </el-radio-group>
              <el-button size="mini" :disabled="!activeDocId" :loading="savingContent" @click="saveEditedContent">保存编辑</el-button>
            </div>
          </div>
          <div class="content-panel">
            <el-input
              v-model="editorText"
              type="textarea"
              :rows="14"
              resize="vertical"
              :placeholder="contentViewMode === 'cleaned' ? '当前章节暂无清洗后 Markdown' : '当前章节暂无原文内容'"
            />
            <div class="markdown-preview" v-html="renderedMarkdownContent" />
          </div>
        </div>

        <div class="pane right">
          <div v-if="showConcernEditor" class="block">
            <div class="pane-head">
              <div>
                <div class="title">章节关注点</div>
                <div class="muted">{{ currentBrowseSectionLabel }}</div>
              </div>
              <el-button size="mini" type="primary" @click="openConcernDialog">编辑关注点</el-button>
            </div>
            <div v-if="currentConcernPoints.length">
              <div v-for="(item, index) in currentConcernPoints" :key="index" class="list-item">{{ index + 1 }}. {{ item }}</div>
            </div>
            <div v-else class="empty">当前章节暂无关注点。</div>
          </div>

          <div class="block">
            <div class="pane-head">
              <div>
                <div class="title">执行流</div>
                <div class="muted">状态：{{ runStreamStatusLabel }}</div>
              </div>
              <el-button size="mini" :disabled="running || !runStreamLogs.length" @click="clearRunStreamLogs">清空</el-button>
            </div>
            <div v-if="runStreamLogGroups.length" class="stream-log-list">
              <el-collapse v-model="expandedLogSections">
                <el-collapse-item
                  v-for="group in runStreamLogGroups"
                  :key="group.key"
                  :name="group.key"
                >
                  <template slot="title">
                    <span class="stream-group-title">{{ group.label }}</span>
                    <span class="stream-group-count">({{ group.items.length }})</span>
                  </template>
                  <div v-for="item in group.items" :key="item.id" class="stream-log-item">
                    <span class="stream-log-time">{{ item.time }}</span>
                    <span class="stream-log-text">{{ item.text }}</span>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
            <div v-else class="empty">启动预审后，这里会显示执行步骤和检索资料。</div>
          </div>

          <run-history-table :runs="runs" :metric-percent="metricPercent" @select-run="viewRun" />
          <run-metrics-panel v-if="selectedRun" :metrics="selectedRunMetrics" :metric-percent="metricPercent" :metric-number="metricNumber" />
          <retrieval-trace-panel v-if="selectedSectionTrace" :detail="selectedTraceRetrievalDetail" :metric-percent="metricPercent" :metric-number="metricNumber" />
          <section-review-panel
            v-if="selectedDisplayReview"
            :review="selectedDisplayReview"
            :current-browse-section-label="currentBrowseSectionLabel"
            :normalized-supported-points="normalizedSupportedPoints"
            :normalized-unsupported-points="normalizedUnsupportedPoints"
            :normalized-missing-points="normalizedMissingPoints"
            :normalized-risk-points="normalizedRiskPoints"
            :normalized-questions="normalizedQuestions"
            :normalized-evidence-refs="normalizedEvidenceRefs"
            :selected-evidence-groups="selectedEvidenceGroups"
            :feedback-form="feedbackForm"
            :selected-run="selectedRun"
            :submitting-feedback="submittingFeedback"
            :feedback-optimize-result="feedbackOptimizeResult"
            :current-patch-candidates="displayedPatchCandidates"
            :historical-patch-candidates="historicalPatchCandidates"
            :formatted-feedback-analysis="formattedFeedbackAnalysis"
            :formatted-feedback-patch="formattedFeedbackPatch"
            :review-conclusion-label="reviewConclusionLabel"
            :feedback-loop-mode="selectedRunFeedbackLoopMode"
            :feedback-loop-locked="true"
            :selected-prompt-rules="selectedPromptRules"
            @submit-feedback="submitSectionFeedback"
          />
          <div v-else class="empty">选择一个章节并查看对应运行后，可在这里查看预审结果。</div>
        </div>
      </div>
    </el-card>

    <el-dialog title="上传申报资料" :visible.sync="uploadDialog.visible" width="760px" @close="closeUploadDialog">
      <el-form label-width="110px" size="small">
        <el-form-item label="资料类别">
          <el-radio-group v-model="uploadDialog.material_category" @change="normalizeUploadMode">
            <el-radio-button v-for="item in materialCategoryOptions" :key="item" :label="item">{{ item }}</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="上传模式">
          <el-radio-group v-model="uploadDialog.mode">
            <el-radio-button label="zip">压缩包</el-radio-button>
            <el-radio-button label="single">单文件</el-radio-button>
            <el-radio-button :disabled="!(isChemicalPharmacyProject && uploadDialog.material_category === '药学')" label="section">章节文件</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <template v-if="isChemicalPharmacyProject && uploadDialog.material_category === '药学'">
          <el-form-item label="资料分支">
            <el-radio-group v-model="uploadDialog.branch">
              <el-radio-button label="3.2.S">原料药</el-radio-button>
              <el-radio-button label="3.2.P">制剂</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="uploadDialog.mode === 'section'" label="章节选择">
            <el-tree :data="uploadTreeData" node-key="section_id" :props="treeProps" highlight-current @node-click="onUploadSectionSelect" />
            <div class="muted" style="margin-top: 8px">当前章节：{{ uploadDialog.section_name || "未选择" }}</div>
          </el-form-item>
        </template>

        <el-form-item label="上传文件">
          <el-upload
            action="#"
            :auto-upload="false"
            :file-list="uploadDialog.file_list"
            :on-change="onUploadFileChange"
            :on-remove="onUploadFileRemove"
            :multiple="uploadDialog.mode !== 'zip'"
            :limit="uploadDialog.mode === 'zip' ? 1 : 20"
          >
            <el-button size="small">选择文件</el-button>
            <div slot="tip" class="el-upload__tip">支持 pdf / doc / docx / txt / md / zip</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button @click="closeUploadDialog">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">上传资料</el-button>
      </span>
    </el-dialog>

    <el-dialog title="编辑关注点" :visible.sync="concernDialog.visible" width="680px" @close="closeConcernDialog">
      <div v-for="(item, index) in concernDialog.items" :key="`concern-${index}`" class="concern-row">
        <el-input v-model="concernDialog.items[index]" type="textarea" :rows="2" placeholder="输入关注点" />
        <div class="actions concern-actions">
          <el-button size="mini" @click="insertConcernRow(index)">下方插入</el-button>
          <el-button size="mini" type="danger" @click="removeConcernRow(index)">删除</el-button>
        </div>
      </div>
      <div class="actions" style="margin-top: 12px">
        <el-button size="mini" @click="appendConcernRow">新增一行</el-button>
      </div>
      <span slot="footer">
        <el-button @click="closeConcernDialog">取消</el-button>
        <el-button type="primary" :loading="savingConcernPoints" @click="confirmConcernDialog">保存</el-button>
      </span>
    </el-dialog>

    <el-dialog title="原文件预览" :visible.sync="previewDialog.visible" width="88%" top="4vh" @close="closePreviewDialog">
      <div class="preview-meta">
        <span>文件：{{ activeDocLabel }}</span>
        <span>类型：{{ activeFileType || "-" }}</span>
      </div>
      <div v-if="previewUrl" class="preview-frame-wrap">
        <iframe :src="previewUrl" class="preview-frame" frameborder="0" />
      </div>
      <div v-else class="empty">当前没有可预览文件。</div>
      <span slot="footer">
        <el-button @click="closePreviewDialog">关闭</el-button>
        <el-button v-if="previewUrl" type="primary" @click="openPreviewInNewTab">新窗口打开</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import {
  addFeedback,
  ctdCatalog,
  listSubmissions,
  optimizeFeedback,
  preReviewStreamUrl,
  projectDetail,
  runHistory,
  replaySection,
  saveSubmissionContent,
  sectionOverview,
  sectionPatchCandidates,
  sectionTraces,
  submissionContent,
  submissionPreviewUrl,
  updateSectionConcerns,
  uploadSubmission,
} from "@/api/prereview";
import { SUBMISSION_MATERIAL_CATEGORIES } from "@/constants/registration";
import RetrievalTracePanel from "@/components/pre-review/RetrievalTracePanel.vue";
import RunHistoryTable from "@/components/pre-review/RunHistoryTable.vue";
import RunMetricsPanel from "@/components/pre-review/RunMetricsPanel.vue";
import SectionReviewPanel from "@/components/pre-review/SectionReviewPanel.vue";

function cloneTree(nodes) {
  return Array.isArray(nodes) ? JSON.parse(JSON.stringify(nodes)) : [];
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeStringList(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function normalizeQuestionList(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => ({
    issue: String((item && item.issue) || "").trim(),
    basis: String((item && item.basis) || "").trim(),
    requested_action: String((item && item.requested_action) || "").trim(),
  })).filter((item) => item.issue || item.basis || item.requested_action);
}

function renderSimpleMarkdown(text) {
  const source = String(text || "").trim();
  if (!source) {
    return '<div class="empty-markdown">暂无可预览内容。</div>';
  }
  const lines = source.split(/\r?\n/);
  const html = [];
  let inUl = false;
  let inOl = false;
  let tableBuffer = [];
  const flushLists = () => {
    if (inUl) {
      html.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      html.push("</ol>");
      inOl = false;
    }
  };
  const flushTable = () => {
    if (!tableBuffer.length) {
      return;
    }
    const rows = tableBuffer.map((line) => line.split("|").slice(1, -1).map((cell) => escapeHtml(cell.trim())));
    tableBuffer = [];
    html.push('<table class="md-table"><tbody>');
    rows.forEach((row, rowIndex) => {
      if (rowIndex === 1 && row.every((cell) => /^-+$/.test(cell))) {
        return;
      }
      html.push("<tr>");
      row.forEach((cell) => {
        html.push(rowIndex === 0 ? `<th>${cell}</th>` : `<td>${cell}</td>`);
      });
      html.push("</tr>");
    });
    html.push("</tbody></table>");
  };
  lines.forEach((rawLine) => {
    const trimmed = String(rawLine || "").trim();
    if (!trimmed) {
      flushLists();
      flushTable();
      html.push('<div class="md-space"></div>');
      return;
    }
    if (trimmed.startsWith("|")) {
      flushLists();
      tableBuffer.push(trimmed);
      return;
    }
    flushTable();
    if (/^###\s+/.test(trimmed)) {
      flushLists();
      html.push(`<h4>${escapeHtml(trimmed.replace(/^###\s+/, ""))}</h4>`);
      return;
    }
    if (/^##\s+/.test(trimmed)) {
      flushLists();
      html.push(`<h3>${escapeHtml(trimmed.replace(/^##\s+/, ""))}</h3>`);
      return;
    }
    if (/^#\s+/.test(trimmed)) {
      flushLists();
      html.push(`<h2>${escapeHtml(trimmed.replace(/^#\s+/, ""))}</h2>`);
      return;
    }
    if (/^-\s+/.test(trimmed)) {
      if (inOl) {
        html.push("</ol>");
        inOl = false;
      }
      if (!inUl) {
        html.push("<ul>");
        inUl = true;
      }
      html.push(`<li>${escapeHtml(trimmed.replace(/^-\s+/, ""))}</li>`);
      return;
    }
    if (/^\d+\.\s+/.test(trimmed)) {
      if (inUl) {
        html.push("</ul>");
        inUl = false;
      }
      if (!inOl) {
        html.push("<ol>");
        inOl = true;
      }
      html.push(`<li>${escapeHtml(trimmed.replace(/^\d+\.\s+/, ""))}</li>`);
      return;
    }
    flushLists();
    html.push(`<p>${escapeHtml(trimmed)}</p>`);
  });
  flushLists();
  flushTable();
  return html.join("");
}

export default {
  name: "PreReviewSession",
  components: {
    RetrievalTracePanel,
    RunHistoryTable,
    RunMetricsPanel,
    SectionReviewPanel,
  },
  data() {
    return {
      projectId: this.$route.params.projectId,
      project: {},
      ctdCatalogData: [],
      submissions: [],
      runs: [],
      resultOverview: null,
      sectionTraceMap: {},
      sectionPatchMap: {},
      currentBrowseSectionId: "",
      activeDocId: "",
      activeFileType: "",
      previewUrl: "",
      contentSections: [],
      contentViewMode: "cleaned",
      editorText: "",
      treeProps: { children: "children_sections", label: "label" },
      running: false,
      savingContent: false,
      runningSection: false,
      uploading: false,
      submittingFeedback: false,
      savingConcernPoints: false,
      selectedRun: null,
      feedbackForm: { decision: "valid", feedback_text: "", enableOptimize: true },
      feedbackOptimizeResult: {
        feedback_key: "",
        analysis_result: null,
        patch_result: null,
        feedback_optimize_status: "",
        candidate_register_status: "",
        replay_status: "",
        error_message: "",
      },
      experimentConfig: { enableFeedbackOptimize: true },
      runEventSource: null,
      runStreamStatus: "idle",
      runStreamLogs: [],
      expandedLogSections: ["__run__"],
      viewFilters: { domain: "药学", branch: "all" },
      uploadDialog: { visible: false, material_category: "药学", branch: "3.2.S", mode: "single", section_id: "", section_name: "", file_list: [] },
      concernDialog: { visible: false, items: [] },
      previewDialog: { visible: false },
    };
  },
  computed: {
    materialCategoryOptions() {
      return SUBMISSION_MATERIAL_CATEGORIES || ["药学", "临床", "非临床"];
    },
    isChemicalPharmacyProject() {
      return this.project.registration_scope === "化学药";
    },
    showPharmacyBranchSelector() {
      return this.viewFilters.domain === "药学";
    },
    leftTreeData() {
      return this.decorateCatalogTree(this.filteredCatalogTree(this.ctdCatalogData, this.viewFilters.branch));
    },
    uploadTreeData() {
      return this.filteredCatalogTree(this.ctdCatalogData, this.uploadDialog.branch);
    },
    filteredSubmissions() {
      return (this.submissions || []).filter((item) => {
        const material = String((item && item.material_category) || "").trim();
        if (this.viewFilters.domain && material && material !== this.viewFilters.domain) {
          return false;
        }
        if (this.showPharmacyBranchSelector && this.viewFilters.branch !== "all") {
          const sid = String((item && item.section_id) || "").trim();
          if (sid && !sid.startsWith(this.viewFilters.branch)) {
            return false;
          }
        }
        return true;
      });
    },
    currentBrowseFiles() {
      const sid = String(this.currentBrowseSectionId || "").trim();
      if (!sid) {
        return this.filteredSubmissions;
      }
      const matched = this.filteredSubmissions.filter((item) => {
        const currentId = String((item && item.section_id) || "").trim();
        const sectionPath = Array.isArray(item.section_path) ? item.section_path.map((x) => String(x || "")) : [];
        return currentId === sid || currentId.startsWith(`${sid}.`) || sectionPath.some((x) => x === sid || x.startsWith(`${sid}.`));
      });
      return matched.length ? matched : this.filteredSubmissions;
    },
    currentBrowseSection() {
      return this.findTreeNode(this.leftTreeData, this.currentBrowseSectionId);
    },
    currentContentSection() {
      const sid = String(this.currentBrowseSectionId || "").trim();
      const list = Array.isArray(this.contentSections) ? this.contentSections : [];
      return list.find((item) => String((item && item.section_id) || "").trim() === sid) || list[0] || null;
    },
    activeDocLabel() {
      const row = this.submissions.find((item) => item.doc_id === this.activeDocId);
      return row ? row.file_name : "未选择文件";
    },
    currentBrowseSectionLabel() {
      const current = this.currentBrowseSection;
      return current ? (current.section_name || current.label || current.section_id || "当前章节") : "当前章节";
    },
    currentContentSectionLabel() {
      const current = this.currentContentSection;
      return current ? (current.section_name || current.section_title || current.section_id || "当前章节") : "当前章节";
    },
    renderedMarkdownContent() {
      return renderSimpleMarkdown(this.editorText);
    },
    showConcernEditor() {
      return this.viewFilters.domain === "药学";
    },
    currentConcernPoints() {
      return normalizeStringList(this.currentBrowseSection && this.currentBrowseSection.concern_points);
    },
    selectedRunMetrics() {
      const metrics = (this.selectedRun && this.selectedRun.metrics) || {};
      return { review: metrics.review || {}, retrieval: metrics.retrieval || {}, feedback: metrics.feedback || {}, trajectory: metrics.trajectory || {} };
    },
    selectedRunFeedbackLoopMode() {
      return (this.selectedRun && this.selectedRun.feedback_loop_mode) || "feedback_optimize";
    },
    runStreamStatusLabel() {
      const mapping = {
        idle: "未开始",
        connecting: "连接中",
        running: "执行中",
        completed: "已完成",
        failed: "失败",
      };
      return mapping[this.runStreamStatus] || this.runStreamStatus || "-";
    },
    runStreamLogGroups() {
      const groups = [];
      const buckets = {};
      (this.runStreamLogs || []).forEach((item) => {
        const key = item.sectionKey || "__run__";
        if (!buckets[key]) {
          buckets[key] = {
            key,
            label: item.sectionLabel || "运行级事件",
            items: [],
          };
          groups.push(buckets[key]);
        }
        buckets[key].items.push(item);
      });
      return groups;
    },
    selectedSectionTrace() {
      return this.sectionTraceMap[this.currentBrowseSectionId] || null;
    },
    selectedTraceRetrievalDetail() {
      const detail = (this.selectedSectionTrace && this.selectedSectionTrace.retrieval_detail) || {};
      return { metrics: detail.metrics || {}, source_breakdown: detail.source_breakdown || {}, error_breakdown: detail.error_breakdown || {} };
    },
    selectedDisplayReview() {
      if (!this.resultOverview) {
        return null;
      }
      const sid = this.currentBrowseSectionId;
      const standardized = (this.resultOverview.standardized_output_by_section_id || {})[sid];
      if (standardized) {
        return standardized;
      }
      const sectionOutput = (this.resultOverview.section_output_by_section_id || {})[sid];
      if (sectionOutput) {
        return sectionOutput;
      }
      const conclusion = (this.resultOverview.conclusion_by_section_id || {})[sid];
      return conclusion && conclusion.standard_output ? conclusion.standard_output : null;
    },
    selectedEvidenceGroups() {
      const materials = Array.isArray(this.selectedSectionTrace && this.selectedSectionTrace.retrieved_materials) ? this.selectedSectionTrace.retrieved_materials : [];
      const buckets = {};
      materials.forEach((item) => {
        const source = String(item.source_type || item.source_domain || item.category || item.classification || "其他").trim() || "其他";
        if (!buckets[source]) {
          buckets[source] = [];
        }
        buckets[source].push(item);
      });
      return Object.keys(buckets).map((key) => ({ source: key, items: buckets[key] }));
    },
    normalizedSupportedPoints() {
      return normalizeStringList(this.selectedDisplayReview && this.selectedDisplayReview.supported_points);
    },
    normalizedUnsupportedPoints() {
      return normalizeStringList(this.selectedDisplayReview && this.selectedDisplayReview.unsupported_points);
    },
    normalizedMissingPoints() {
      return normalizeStringList(this.selectedDisplayReview && this.selectedDisplayReview.missing_points);
    },
    normalizedRiskPoints() {
      return normalizeStringList(this.selectedDisplayReview && this.selectedDisplayReview.risk_points);
    },
    normalizedQuestions() {
      return normalizeQuestionList(this.selectedDisplayReview && this.selectedDisplayReview.questions);
    },
    normalizedEvidenceRefs() {
      return normalizeStringList(this.selectedDisplayReview && this.selectedDisplayReview.evidence_refs);
    },
    formattedFeedbackAnalysis() {
      return JSON.stringify(this.feedbackOptimizeResult.analysis_result || {}, null, 2);
    },
    formattedFeedbackPatch() {
      return JSON.stringify(this.feedbackOptimizeResult.patch_result || {}, null, 2);
    },
    displayedPatchCandidates() {
      const patchResult = this.feedbackOptimizeResult.patch_result;
      return patchResult && typeof patchResult === "object" && Array.isArray(patchResult.patches) ? patchResult.patches : [];
    },
    historicalPatchCandidates() {
      return Array.isArray(this.sectionPatchMap[this.currentBrowseSectionId]) ? this.sectionPatchMap[this.currentBrowseSectionId] : [];
    },
    selectedPromptRules() {
      const promptRules = this.selectedSectionTrace && this.selectedSectionTrace.prompt_rules && typeof this.selectedSectionTrace.prompt_rules === "object"
        ? this.selectedSectionTrace.prompt_rules
        : {};
      return {
        planner: Array.isArray(promptRules.planner) ? promptRules.planner : [],
        reviewer: Array.isArray(promptRules.reviewer) ? promptRules.reviewer : [],
      };
    },
  },
  watch: {
    currentBrowseSectionId() {
      this.syncEditorToCurrentSection();
    },
    contentViewMode() {
      this.syncEditorToCurrentSection();
    },
  },
  async mounted() {
    await this.loadProject();
    await this.loadCatalog();
    await this.loadSubmissions();
    await this.loadRuns();
  },
  beforeDestroy() {
    this.closeRunEventSource();
  },
  methods: {
    reviewConclusionLabel(value) {
      const mapping = { supported: "支持", unsupported: "不支持", insufficient_information: "信息不足", need_more_information: "需补充信息", risk: "存在风险" };
      return mapping[String(value || "").trim()] || value || "-";
    },
    metricPercent(value) {
      const num = Number(value);
      return Number.isFinite(num) ? `${(num * 100).toFixed(1)}%` : "-";
    },
    metricNumber(value) {
      const num = Number(value);
      return Number.isFinite(num) ? `${num}` : "-";
    },
    clearRunStreamLogs() {
      this.runStreamLogs = [];
      this.expandedLogSections = ["__run__"];
      if (!this.running) {
        this.runStreamStatus = "idle";
      }
    },
    closeRunEventSource() {
      if (this.runEventSource) {
        this.runEventSource.close();
        this.runEventSource = null;
      }
    },
    parseStreamEventData(raw) {
      try {
        return raw ? JSON.parse(raw) : {};
      } catch (_) {
        return { message: String(raw || "") };
      }
    },
    appendRunStreamLog(type, payload) {
      const data = payload && typeof payload === "object" ? payload : { message: String(payload || "") };
      const text = this.formatRunStreamMessage(type, data);
      if (!text) {
        return;
      }
      const now = new Date();
      const time = [now.getHours(), now.getMinutes(), now.getSeconds()].map((item) => String(item).padStart(2, "0")).join(":");
      this.runStreamLogs.push({
        id: `${Date.now()}_${this.runStreamLogs.length + 1}`,
        type,
        stage: data.stage || type,
        sectionKey: payload.section_id ? String(payload.section_id) : "__run__",
        sectionLabel: payload.section_id ? [payload.section_id, payload.section_name].filter(Boolean).join(" ") : "运行级事件",
        time,
        text,
      });
      const sectionKey = payload.section_id ? String(payload.section_id) : "__run__";
      if (!this.expandedLogSections.includes(sectionKey)) {
        this.expandedLogSections.push(sectionKey);
      }
      if (this.runStreamLogs.length > 300) {
        this.runStreamLogs.splice(0, this.runStreamLogs.length - 300);
      }
    },
    formatRunStreamMessage(type, payload) {
      const stage = String((payload && payload.stage) || "").trim();
      const message = String((payload && payload.message) || "").trim();
      const sectionLabel = [payload.section_id, payload.section_name].filter(Boolean).join(" ");
      const prefix = sectionLabel ? `[${sectionLabel}] ` : "";
      if (type === "error" && message) {
        return message;
      }
      switch (stage) {
        case "stream_open":
          return "SSE 连接已建立。";
        case "run_start":
        case "chunks_loaded":
        case "run_created":
        case "section_queue":
        case "planner_start":
        case "planner_done":
        case "retrieval_start":
        case "retrieval_done":
        case "reviewer_start":
        case "reviewer_done":
        case "run_done":
        case "run_failed":
          return `${prefix}${message}`;
        case "section_start":
          return `${prefix}${message || "开始处理章节。"}`;
        case "section_done":
          return `${prefix}${message}${payload.conclusion ? ` 结论：${payload.conclusion}` : ""}`;
        case "section_skipped":
          return `${prefix}${message || "章节已跳过。"}`;
        case "retrieval_source_start":
          return `${prefix}开始检索${payload.source_type || "资料"}。`;
        case "retrieval_query":
          return `${prefix}检索${payload.source_type || "资料"}：${payload.query || message}`;
        case "retrieval_source_done":
          return `${prefix}${payload.source_type || "资料"}检索完成，命中 ${payload.hit_count ?? 0} 条。${Array.isArray(payload.hit_titles) && payload.hit_titles.length ? ` 命中标题：${payload.hit_titles.join("；")}` : ""}`;
        default:
          return `${prefix}${message || stage || type || "执行中"}`;
      }
    },
    buildRunPayload() {
      const sectionFocusOverrides = {};
      const walk = (nodes) => {
        (nodes || []).forEach((node) => {
          if (!node || typeof node !== "object") return;
          const sid = String(node.section_id || "").trim();
          const points = normalizeStringList(node.concern_points);
          if (sid && points.length) {
            sectionFocusOverrides[sid] = points;
          }
          walk(node.children_sections || []);
        });
      };
      walk(this.leftTreeData);
      return {
        project_id: this.projectId,
        source_doc_id: this.activeDocId,
        run_config: {
          domain: this.viewFilters.domain,
          branch: this.viewFilters.branch,
          strategy: "single_section_pre_review_v2",
          workflow_mode: "single_section_pre_review_v2",
          feedback_loop_mode: this.experimentConfig.enableFeedbackOptimize ? "feedback_optimize" : "feedback_only",
          enable_feedback_optimize: !!this.experimentConfig.enableFeedbackOptimize,
          section_focus_overrides: sectionFocusOverrides,
        },
      };
    },
    openRunStream(payload) {
      return new Promise((resolve, reject) => {
        this.closeRunEventSource();
        const source = new EventSource(preReviewStreamUrl(payload));
        let settled = false;
        this.runEventSource = source;
        this.runStreamStatus = "connecting";
        source.onopen = () => {
          this.runStreamStatus = "running";
          this.appendRunStreamLog("progress", { stage: "stream_open" });
        };
        source.addEventListener("progress", (event) => {
          this.appendRunStreamLog("progress", this.parseStreamEventData(event.data));
        });
        source.addEventListener("done", (event) => {
          const data = this.parseStreamEventData(event.data);
          settled = true;
          this.runStreamStatus = "completed";
          this.appendRunStreamLog("progress", { stage: "run_done", message: data.message || "预审任务完成。" });
          this.closeRunEventSource();
          resolve(data);
        });
        source.addEventListener("error", (event) => {
          if (typeof event.data !== "string" || !event.data) {
            return;
          }
          const data = this.parseStreamEventData(event.data);
          settled = true;
          this.runStreamStatus = "failed";
          this.appendRunStreamLog("error", data);
          this.closeRunEventSource();
          reject(new Error(data.message || "预审执行失败"));
        });
        source.onerror = () => {
          if (settled) {
            return;
          }
          this.runStreamStatus = "failed";
          this.appendRunStreamLog("error", { message: "SSE 连接中断。" });
          this.closeRunEventSource();
          reject(new Error("SSE 连接中断"));
        };
      });
    },
    decorateCatalogTree(nodes) {
      return (nodes || []).map((item) => ({ ...item, label: [item.section_id, item.section_name].filter(Boolean).join(" "), children_sections: this.decorateCatalogTree(item.children_sections || []) }));
    },
    filteredCatalogTree(nodes, branch = "all") {
      const visit = (list) => (list || []).map((item) => {
        const children = visit(item.children_sections || []);
        const sid = String(item.section_id || "");
        const keep = branch === "all" || sid.startsWith(branch) || children.length > 0;
        return keep ? { ...item, children_sections: children } : null;
      }).filter(Boolean);
      return visit(cloneTree(nodes));
    },
    firstTreeNodeId(nodes) {
      const list = Array.isArray(nodes) ? nodes : [];
      if (!list.length) {
        return "";
      }
      const head = list[0];
      return head.section_id || this.firstTreeNodeId(head.children_sections || []);
    },
    findTreeNode(nodes, sectionId) {
      for (const item of nodes || []) {
        if (item.section_id === sectionId) {
          return item;
        }
        const child = this.findTreeNode(item.children_sections || [], sectionId);
        if (child) {
          return child;
        }
      }
      return null;
    },
    onBrowseSectionSelect(node) {
      this.currentBrowseSectionId = node.section_id;
      if (this.currentBrowseFiles.length && !this.currentBrowseFiles.some((item) => item.doc_id === this.activeDocId)) {
        this.activeDocId = this.currentBrowseFiles[0].doc_id;
        this.onDocChange(this.activeDocId);
      }
    },
    async loadProject() {
      try {
        const res = await projectDetail(this.projectId);
        this.project = (res && res.data) || {};
      } catch (_) {
        this.project = {};
      }
    },
    async loadCatalog() {
      try {
        const res = await ctdCatalog(this.projectId);
        const data = (res && res.data) || {};
        this.ctdCatalogData = cloneTree(data.chapter_structure || []);
      } catch (_) {
        this.ctdCatalogData = [];
      }
      if (!this.currentBrowseSectionId) {
        this.currentBrowseSectionId = this.firstTreeNodeId(this.filteredCatalogTree(this.ctdCatalogData, this.viewFilters.branch));
      }
    },
    async loadSubmissions() {
      try {
        const res = await listSubmissions(this.projectId, { page: 1, page_size: 500 });
        this.submissions = ((res && res.data && res.data.list) || []).map((item) => ({ ...item, section_path: Array.isArray(item.section_path) ? item.section_path : [] }));
      } catch (_) {
        this.submissions = [];
      }
      this.ensureActiveDoc();
    },
    async loadRuns() {
      try {
        const res = await runHistory({ project_id: this.projectId });
        this.runs = (res && res.data) || [];
        if (this.runs.length && !this.selectedRun) {
          await this.viewRun(this.runs[0]);
        }
      } catch (_) {
        this.runs = [];
        this.selectedRun = null;
        this.resultOverview = null;
      }
    },
    async onViewFilterChange() {
      if (!this.showPharmacyBranchSelector) {
        this.viewFilters.branch = "all";
      }
      this.currentBrowseSectionId = this.firstTreeNodeId(this.filteredCatalogTree(this.ctdCatalogData, this.viewFilters.branch));
      this.ensureActiveDoc();
      if (this.selectedRun) {
        await this.viewRun(this.selectedRun);
      }
    },
    ensureActiveDoc() {
      if (!this.filteredSubmissions.length) {
        this.activeDocId = "";
        this.previewUrl = "";
        this.editorText = "";
        return;
      }
      const candidates = this.currentBrowseFiles.length ? this.currentBrowseFiles : this.filteredSubmissions;
      if (!candidates.some((item) => item.doc_id === this.activeDocId)) {
        this.activeDocId = candidates[0].doc_id;
      }
      this.onDocChange(this.activeDocId);
    },
    syncActiveDocMeta(docId) {
      const row = this.submissions.find((item) => item.doc_id === docId);
      this.activeFileType = row ? row.file_type : "";
      this.previewUrl = row ? submissionPreviewUrl(this.projectId, docId) : "";
    },
    async onDocChange(docId) {
      if (!docId) {
        this.previewUrl = "";
        this.editorText = "";
        this.contentSections = [];
        return;
      }
      this.activeDocId = docId;
      this.syncActiveDocMeta(docId);
      await this.loadSubmissionText(docId);
    },
    async loadSubmissionText(docId) {
      try {
        const res = await submissionContent(this.projectId, docId);
        const data = (res && res.data) || {};
        this.contentSections = Array.isArray(data.sections) ? data.sections : [];
        this.syncEditorToCurrentSection(data.display_content || data.content || "");
      } catch (_) {
        this.editorText = "";
        this.contentSections = [];
      }
    },
    syncEditorToCurrentSection(fallbackContent = "") {
      const current = this.currentContentSection;
      const rawText = (current && (current.raw_content || current.content)) || fallbackContent || "";
      const cleanedText = (current && (current.cleaned_markdown || current.display_content)) || rawText;
      this.editorText = this.contentViewMode === "raw" ? rawText : cleanedText;
    },
    async saveEditedContent() {
      if (!this.activeDocId) {
        return this.$message.warning("请先选择文件。");
      }
      this.savingContent = true;
      try {
        await saveSubmissionContent(this.projectId, this.activeDocId, { content: this.editorText || "" });
        this.$message.success("章节内容已保存。");
        await this.loadSubmissionText(this.activeDocId);
      } catch (e) {
        this.$message.error((e && e.message) || "保存失败");
      } finally {
        this.savingContent = false;
      }
    },
    async run() {
      if (!this.activeDocId) {
        return this.$message.warning("请先选择文件。");
      }
      this.running = true;
      this.runStreamLogs = [];
      this.expandedLogSections = ["__run__"];
      this.runStreamStatus = "connecting";
      try {
        const res = await this.openRunStream(this.buildRunPayload());
        this.$message.success((res && res.message) || "预审已完成");
        this.selectedRun = null;
        await this.loadRuns();
      } catch (e) {
        this.$message.error((e && e.message) || "启动预审失败");
      } finally {
        this.running = false;
        if (this.runStreamStatus === "connecting") {
          this.runStreamStatus = "idle";
        }
      }
    },
    async runCurrentSectionReview() {
      if (!this.activeDocId) {
        return this.$message.warning("请先选择文件。");
      }
      if (!this.currentBrowseSectionId) {
        return this.$message.warning("请先选择章节。");
      }
      this.runningSection = true;
      try {
        const res = await replaySection(this.projectId, this.activeDocId, this.currentBrowseSectionId, {
          run_config: this.buildRunPayload().run_config,
        });
        const data = (res && res.data) || {};
        const runId = String(data.run_id || "").trim();
        this.$message.success((res && res.message) || "当前章节审评已完成");
        await this.loadRuns();
        if (runId) {
          const matched = this.runs.find((item) => item.run_id === runId);
          if (matched) {
            await this.viewRun(matched);
          }
        }
      } catch (e) {
        this.$message.error((e && e.message) || "当前章节审评失败");
      } finally {
        this.runningSection = false;
      }
    },
    async viewRun(row) {
      if (!row || !row.run_id) {
        return;
      }
      this.selectedRun = row;
      this.feedbackForm.enableOptimize = (row.feedback_loop_mode || "feedback_optimize") !== "feedback_only";
      this.feedbackOptimizeResult = {
        feedback_key: "",
        analysis_result: null,
        patch_result: null,
        feedback_optimize_status: "",
        candidate_register_status: "",
        replay_status: "",
        error_message: "",
      };
      try {
        const [overviewRes, traceRes, patchRes] = await Promise.all([sectionOverview(row.run_id), sectionTraces(row.run_id, {}), sectionPatchCandidates(row.run_id, {})]);
        this.resultOverview = (overviewRes && overviewRes.data) || null;
        const traces = (traceRes && traceRes.data) || [];
        this.sectionTraceMap = Array.isArray(traces)
          ? traces.reduce((acc, item) => {
              if (item && item.section_id) {
                acc[item.section_id] = item;
              }
              return acc;
            }, {})
          : {};
        const patches = (patchRes && patchRes.data) || [];
        this.sectionPatchMap = Array.isArray(patches)
          ? patches.reduce((acc, item) => {
              const sid = String((item && item.section_id) || "").trim();
              if (!sid) {
                return acc;
              }
              if (!acc[sid]) {
                acc[sid] = [];
              }
              acc[sid].push(item);
              return acc;
            }, {})
          : {};
      } catch (_) {
        this.resultOverview = null;
        this.sectionTraceMap = {};
        this.sectionPatchMap = {};
      }
    },
    currentEditorBaselineText() {
      const current = this.currentContentSection;
      if (!current) {
        return "";
      }
      const rawText = String(current.raw_content || current.content || "").trim();
      const cleanedText = String(current.cleaned_markdown || current.display_content || "").trim();
      return this.contentViewMode === "raw" ? rawText : cleanedText || rawText;
    },
    async submitSectionFeedback() {
      if (!this.selectedRun || !this.selectedDisplayReview) {
        return this.$message.warning("请先选择一个章节审评结果。");
      }
      this.submittingFeedback = true;
      try {
        const payload = {
          section_id: this.selectedDisplayReview.section_id || this.currentBrowseSectionId,
          decision: this.feedbackForm.decision,
          feedback_type: this.feedbackForm.decision,
          chain_mode: this.selectedRunFeedbackLoopMode === "feedback_only" ? "feedback_only" : "feedback_optimize",
          manual_modified: this.currentEditorBaselineText().trim() !== String(this.editorText || "").trim(),
          original_output: this.selectedDisplayReview,
          revised_output: { edited_content: this.editorText || "" },
          feedback_text: this.feedbackForm.feedback_text || "",
          operator: "reviewer",
        };
        if (this.selectedRunFeedbackLoopMode !== "feedback_only") {
          const res = await optimizeFeedback(this.selectedRun.run_id, payload);
          const data = (res && res.data) || {};
          const chapterLoop = data.chapter_feedback_loop || {};
          this.feedbackOptimizeResult = {
            feedback_key: chapterLoop.feedback_key || "",
            analysis_result: chapterLoop.analysis_result || null,
            patch_result: chapterLoop.patch_result || null,
            feedback_optimize_status: chapterLoop.feedback_optimize_status || "",
            candidate_register_status: chapterLoop.candidate_register_status || "",
            replay_status: chapterLoop.replay_status || "",
            error_message: chapterLoop.error_message || "",
          };
          this.$message.success("反馈已提交，并进入优化回路。");
        } else {
          await addFeedback(this.selectedRun.run_id, payload);
          this.feedbackOptimizeResult = {
            feedback_key: "",
            analysis_result: null,
            patch_result: null,
            feedback_optimize_status: "",
            candidate_register_status: "",
            replay_status: "",
            error_message: "",
          };
          this.$message.success("反馈已记录，未启用优化回路。");
        }
        await this.loadRuns();
        if (this.selectedRun) {
          const matched = this.runs.find((item) => item.run_id === this.selectedRun.run_id) || this.selectedRun;
          await this.viewRun(matched);
        }
      } catch (e) {
        this.$message.error((e && e.message) || "提交反馈失败");
      } finally {
        this.submittingFeedback = false;
      }
    },
    openConcernDialog() {
      this.concernDialog.visible = true;
      this.concernDialog.items = this.currentConcernPoints.length ? [...this.currentConcernPoints] : [""];
    },
    closeConcernDialog() {
      this.concernDialog.visible = false;
      this.concernDialog.items = [];
    },
    openPreviewDialog() {
      if (!this.activeDocId || !this.previewUrl) {
        this.$message.warning("请先选择可预览文件。");
        return;
      }
      this.previewDialog.visible = true;
    },
    closePreviewDialog() {
      this.previewDialog.visible = false;
    },
    openPreviewInNewTab() {
      if (!this.previewUrl) {
        return;
      }
      window.open(this.previewUrl, "_blank");
    },
    appendConcernRow() {
      this.concernDialog.items.push("");
    },
    insertConcernRow(index) {
      this.concernDialog.items.splice(index + 1, 0, "");
    },
    removeConcernRow(index) {
      this.concernDialog.items.splice(index, 1);
    },
    async confirmConcernDialog() {
      const points = (this.concernDialog.items || []).map((item) => String(item || "").trim()).filter(Boolean);
      if (!this.currentBrowseSectionId) {
        return;
      }
      this.savingConcernPoints = true;
      try {
        await updateSectionConcerns(this.projectId, this.currentBrowseSectionId, { concern_points: points });
        await this.loadCatalog();
        this.$message.success("关注点已保存。");
        this.closeConcernDialog();
      } catch (e) {
        this.$message.error((e && e.message) || "保存关注点失败");
      } finally {
        this.savingConcernPoints = false;
      }
    },
    openUploadDialog() {
      this.uploadDialog.visible = true;
      this.uploadDialog.material_category = this.viewFilters.domain || "药学";
      this.uploadDialog.branch = this.viewFilters.branch === "all" ? "3.2.S" : this.viewFilters.branch;
      this.uploadDialog.mode = this.uploadDialog.material_category === "药学" && this.isChemicalPharmacyProject ? "zip" : "single";
      this.uploadDialog.section_id = "";
      this.uploadDialog.section_name = "";
      this.uploadDialog.file_list = [];
      this.normalizeUploadMode();
    },
    closeUploadDialog() {
      this.uploadDialog.visible = false;
      this.uploadDialog.file_list = [];
    },
    onUploadFileChange(file, fileList) {
      this.uploadDialog.file_list = fileList.slice();
    },
    onUploadFileRemove(file, fileList) {
      this.uploadDialog.file_list = fileList.slice();
    },
    onUploadSectionSelect(node) {
      this.uploadDialog.section_id = node.section_id;
      this.uploadDialog.section_name = node.section_name || node.label || "";
    },
    normalizeUploadMode() {
      const allowSectionMode = this.isChemicalPharmacyProject && this.uploadDialog.material_category === "药学";
      if (!allowSectionMode && this.uploadDialog.mode === "section") {
        this.uploadDialog.mode = "single";
      }
      if (this.uploadDialog.mode !== "section") {
        this.uploadDialog.section_id = "";
        this.uploadDialog.section_name = "";
      }
    },
    async submitUpload() {
      this.normalizeUploadMode();
      if (!this.uploadDialog.file_list.length) {
        return this.$message.warning("请先选择待上传文件。");
      }
      if (this.isChemicalPharmacyProject && this.uploadDialog.material_category === "药学" && this.uploadDialog.mode === "section" && !this.uploadDialog.section_id) {
        return this.$message.warning("章节模式下请先选择章节。");
      }
      const formData = new FormData();
      this.uploadDialog.file_list.forEach((item) => formData.append("files", item.raw || item));
      formData.append("material_category", this.uploadDialog.material_category);
      formData.append("mode", this.uploadDialog.mode || "single");
      if (this.uploadDialog.section_id) {
        formData.append("section_id", this.uploadDialog.section_id);
      } else if (this.isChemicalPharmacyProject && this.uploadDialog.material_category === "药学" && this.uploadDialog.branch && this.uploadDialog.mode !== "section") {
        formData.append("section_id", this.uploadDialog.branch);
      }
      this.uploading = true;
      try {
        const res = await uploadSubmission(this.projectId, formData);
        this.$message.success((res && res.message) || "资料上传成功");
        this.closeUploadDialog();
        await this.loadCatalog();
        await this.loadSubmissions();
      } catch (e) {
        this.$message.error((e && e.message) || "资料上传失败");
      } finally {
        this.uploading = false;
      }
    },
  },
};
</script>

<style scoped>
.session-page { display: flex; flex-direction: column; gap: 16px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.meta-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; color: #5a667a; font-size: 12px; }
.clickable { cursor: pointer; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.workspace { display: grid; grid-template-columns: 280px minmax(0, 1fr) 420px; gap: 16px; min-height: 680px; }
.pane { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.pane-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.title { font-size: 14px; font-weight: 600; color: #2d3648; }
.muted, .empty, .list-item { color: #5a667a; font-size: 12px; line-height: 1.6; }
.actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.block { border: 1px solid #eef1f6; border-radius: 8px; padding: 12px; background: #fff; }
.chapter-tree { flex: 1; overflow: auto; border: 1px solid #eef1f6; border-radius: 8px; padding: 8px; }
.content-panel { display: grid; grid-template-rows: auto 1fr; gap: 12px; min-height: 0; }
.markdown-preview { min-height: 260px; padding: 12px; border: 1px solid #eef1f6; border-radius: 8px; overflow: auto; background: #fafcff; }
.preview-meta { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 12px; color: #5a667a; font-size: 12px; }
.preview-frame-wrap { height: 78vh; border: 1px solid #eef1f6; border-radius: 8px; overflow: hidden; background: #fff; }
.preview-frame { width: 100%; height: 100%; }
.markdown-preview :deep(h2), .markdown-preview :deep(h3), .markdown-preview :deep(h4) { margin: 8px 0; }
.markdown-preview :deep(p) { margin: 0 0 8px; }
.markdown-preview :deep(ul), .markdown-preview :deep(ol) { margin: 0 0 8px 20px; }
.markdown-preview :deep(.md-table) { width: 100%; border-collapse: collapse; }
.markdown-preview :deep(.md-table th), .markdown-preview :deep(.md-table td) { border: 1px solid #dfe6f0; padding: 6px 8px; }
.concern-row { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.concern-actions { justify-content: flex-end; }
.stream-log-list { max-height: 240px; overflow: auto; border: 1px solid #eef1f6; border-radius: 8px; padding: 8px; background: #fafcff; }
.stream-log-item { display: flex; gap: 8px; padding: 4px 0; font-size: 12px; line-height: 1.6; color: #4b5565; }
.stream-log-time { color: #8b96a8; flex: 0 0 64px; }
.stream-log-text { flex: 1; white-space: pre-wrap; word-break: break-word; }
.stream-group-title { font-size: 12px; color: #2d3648; font-weight: 600; }
.stream-group-count { margin-left: 6px; font-size: 12px; color: #8b96a8; }
@media (max-width: 1440px) { .workspace { grid-template-columns: 260px minmax(0, 1fr) 380px; } }
@media (max-width: 1200px) { .workspace { grid-template-columns: 1fr; } }
</style>
