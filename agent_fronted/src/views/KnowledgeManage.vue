<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <h2 class="page-title">知识库管理 - {{ fixedClassification || "全部类别" }}</h2>
        <div class="page-desc">当前页面仅管理该分类下的知识文件，支持查询、语义检索与文件维护</div>
      </div>
      <div class="header-actions">
        <input
          ref="uploadInput"
          class="hidden-upload-input"
          type="file"
          multiple
          accept=".pdf,.doc,.docx,.txt,.md"
          @change="onNativeFileChange"
        />
        <el-button type="primary" :loading="uploading" @click="onPickFiles">上传文件</el-button>
      </div>
    </div>

    <el-card class="k-card">
      <div slot="header">知识查询</div>
      <el-form :inline="true" size="small">
        <el-form-item label="文件名">
          <el-input v-model="filters.file_name" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <el-form :inline="true" size="small" style="margin-top: 8px">
        <el-form-item label="语义检索">
          <el-input v-model="semantic.query" placeholder="请输入问题" style="width: 460px" />
        </el-form-item>
        <el-form-item>
          <el-button :loading="semantic.loading" @click="doSemantic">检索</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="table.list" border class="k-table" style="margin-top: 12px">
        <el-table-column prop="doc_id" label="文件ID" min-width="170" />
        <el-table-column prop="file_name" label="文件名" min-width="220" />
        <el-table-column prop="is_chunked" label="解析状态" width="130">
          <template slot-scope="s">
            <span v-if="s.row.parse_status === 'running' || s.row.parse_status === 'pending'">
              <i class="el-icon-loading" style="margin-right: 4px"></i>解析中
            </span>
            <span v-else-if="s.row.parse_status === 'completed' || s.row.is_chunked">已完成</span>
            <span v-else-if="s.row.parse_status === 'failed'">失败</span>
            <span v-else>未开始</span>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="220">
          <template slot-scope="s">
            <el-progress
              :percentage="Math.round((Number(s.row.parse_progress || 0) || 0) * 100)"
              :status="s.row.parse_status === 'failed' ? 'exception' : (s.row.parse_status === 'completed' || s.row.is_chunked) ? 'success' : undefined"
              :stroke-width="12"
            />
          </template>
        </el-table-column>
        <el-table-column prop="chunk_size" label="分块数" width="90" />
        <el-table-column prop="create_time" label="上传时间" width="170" />
        <el-table-column label="操作" width="280" fixed="right">
          <template slot-scope="scope">
            <el-button
              type="text"
              :disabled="scope.row.parse_status === 'running' || scope.row.parse_status === 'pending'"
              @click="triggerParse(scope.row)"
            >
              解析
            </el-button>
            <el-button type="text" @click="editRow(scope.row)">编辑</el-button>
            <el-button type="text" style="color: #d03050" @click="removeRow(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        style="margin-top: 12px; text-align: right"
        layout="total, prev, pager, next"
        :total="table.total"
        :page-size="table.page_size"
        :current-page.sync="table.page"
        @current-change="search"
      />

      <el-divider>语义检索结果（按文档聚合）</el-divider>
      <el-empty v-if="!semantic.loading && !semantic.grouped_docs.length" description="暂无检索结果" />

      <div class="doc-card-list" v-loading="semantic.loading">
        <el-card v-for="doc in semantic.grouped_docs" :key="doc.doc_id" class="doc-card" shadow="hover">
          <div slot="header" class="doc-card-header">
            <div><span class="doc-id">{{ doc.doc_id }}</span></div>
            <el-tag size="mini" type="info">命中 {{ (doc.matched_hits || []).length }} 条</el-tag>
          </div>

          <div class="doc-summary" v-if="doc.doc_summary">
            <span class="label">整文摘要：</span><span>{{ doc.doc_summary }}</span>
          </div>

          <div class="doc-keywords" v-if="(doc.doc_keywords || []).length">
            <span class="label">整文关键词：</span>
            <el-tag v-for="kw in doc.doc_keywords" :key="`${doc.doc_id}-${kw}`" size="mini" type="success" effect="plain" class="kw-tag">
              {{ kw }}
            </el-tag>
          </div>

          <div class="block-title">命中片段</div>
          <div v-if="!(doc.matched_hits || []).length" class="placeholder">无命中片段</div>
          <div v-for="(hit, idx) in doc.matched_hits || []" :key="`${doc.doc_id}-hit-${idx}`" class="hit-row">
            <div class="hit-meta">
              <el-tag size="mini" type="warning" effect="plain">{{ hit.item_type || "chunk" }}</el-tag>
              <span>chunk: {{ hit.chunk_id || "-" }}</span>
              <span>score: {{ formatScore(hit.score) }}</span>
            </div>
            <div class="hit-summary">{{ hit.summary || "（无摘要）" }}</div>
          </div>

          <el-collapse class="related-collapse">
            <el-collapse-item name="related">
              <template slot="title">
                相关片段（同文组织）
                <el-tag size="mini" type="info" style="margin-left: 8px">{{ (doc.related_chunks || []).length }}</el-tag>
              </template>
              <div v-if="!(doc.related_chunks || []).length" class="placeholder">无相关片段</div>
              <div v-for="(rel, ridx) in doc.related_chunks || []" :key="`${doc.doc_id}-rel-${ridx}`" class="related-row">
                <div class="related-meta">
                  <span>chunk: {{ rel.chunk_id || "-" }}</span>
                  <span>order: {{ rel.chunk_order || "-" }}</span>
                  <span>page: {{ rel.page || "-" }}</span>
                </div>
                <div class="related-summary">{{ rel.summary || "（无摘要）" }}</div>
                <div class="related-text">{{ rel.text || "" }}</div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </div>
    </el-card>

    <el-dialog title="编辑知识" :visible.sync="edit.visible" width="520px">
      <el-form label-width="90px" size="small">
        <el-form-item label="文件名">
          <el-input v-model="edit.file_name" />
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button @click="edit.visible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import { uploadKnowledge, queryKnowledge, semanticQuery, updateKnowledge, deleteKnowledge, parseKnowledge } from "@/api/knowledge";

export default {
  name: "KnowledgeManage",
  data() {
    return {
      classOptions: ["指导原则", "制度规范", "法律法规", "药典数据", "历史经验", "共性问题", "审评规则"],
      uploading: false,
      filters: { file_name: "", keyword: "", file_type: "", classification: "" },
      table: { list: [], total: 0, page: 1, page_size: 10 },
      semantic: { query: "", hits: [], grouped_docs: [], loading: false },
      edit: { visible: false, doc_id: "", file_name: "" },
      progressStream: null,
      querying: false,
      pendingQuery: false,
    };
  },
  computed: {
    fixedClassification() {
      return (this.$route.meta && this.$route.meta.classification) || "";
    },
  },
  watch: {
    "$route.path"() {
      this.applyCategoryFromRoute();
      this.onSearch();
    },
  },
  mounted() {
    this.applyCategoryFromRoute();
    this.search();
    this.openProgressStream();
  },
  beforeDestroy() {
    this.closeProgressStream();
  },
  methods: {
    applyCategoryFromRoute() {
      const c = this.fixedClassification;
      if (!c) return;
      this.filters.classification = c;
    },
    formatScore(v) {
      const n = Number(v);
      return Number.isFinite(n) ? n.toFixed(4) : "-";
    },
    onPickFiles() {
      if (this.uploading) return;
      const input = this.$refs.uploadInput;
      if (!input) return;
      input.value = "";
      input.click();
    },
    async onNativeFileChange(e) {
      const files = Array.from((e && e.target && e.target.files) || []);
      if (!files.length) return;
      await this.uploadSelectedFiles(files);
    },
    async uploadSelectedFiles(files) {
      this.uploading = true;
      let successCount = 0;
      let failCount = 0;
      const classification = this.fixedClassification || this.filters.classification || this.classOptions[0];
      try {
        for (const item of files) {
          const tempId = `temp_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
          const optimisticRow = {
            doc_id: tempId,
            file_name: item.name,
            file_type: item.name && item.name.includes(".") ? item.name.split(".").pop().toLowerCase() : "",
            classification,
            create_time: "",
            is_chunked: false,
            chunk_size: 0,
            parse_status: "pending",
            parse_progress: 0,
          };
          this.table.list.unshift(optimisticRow);
          this.table.list = this.table.list.slice(0, this.table.page_size);

          const fd = new FormData();
          fd.append("file", item);
          fd.append("classification", classification);
          fd.append("affect_range", "other");
          try {
            const res = await uploadKnowledge(fd);
            const meta = (res && res.data) || {};
            const pendingRow = {
              ...meta,
              file_name: meta.file_name || item.name,
              file_type: meta.file_type || (item.name && item.name.includes(".") ? item.name.split(".").pop().toLowerCase() : ""),
              classification: meta.classification || classification,
              create_time: meta.create_time || "",
              is_chunked: false,
              chunk_size: meta.chunk_size || 0,
              parse_status: meta.parse_status || "pending",
              parse_progress: typeof meta.parse_progress === "number" ? meta.parse_progress : 0,
            };
            const tempIndex = this.table.list.findIndex((x) => x.doc_id === tempId);
            if (tempIndex >= 0) {
              this.table.list.splice(tempIndex, 1, pendingRow);
            }
            this.table.total += 1;
            successCount += 1;
          } catch (_) {
            const tempIndex = this.table.list.findIndex((x) => x.doc_id === tempId);
            if (tempIndex >= 0) {
              this.table.list.splice(tempIndex, 1);
            }
            failCount += 1;
          }
        }

        if (successCount > 0 && failCount === 0) {
          this.$message.success("上传成功，后台正在解析");
        } else if (successCount > 0 && failCount > 0) {
          this.$message.warning(`部分上传成功：成功 ${successCount}，失败 ${failCount}`);
        } else {
          this.$message.error("上传失败");
        }
      } finally {
        this.uploading = false;
        this.search();
      }
    },
    onSearch() {
      this.table.page = 1;
      this.applyCategoryFromRoute();
      this.search();
    },
    async search() {
      if (this.querying) {
        this.pendingQuery = true;
        return;
      }
      this.querying = true;
      try {
        const res = await queryKnowledge({
          file_name: this.filters.file_name,
          keyword: this.filters.keyword,
          file_type: this.filters.file_type,
          classification: this.filters.classification,
          page: this.table.page,
          page_size: this.table.page_size,
        });
        this.table.list = (res.data && res.data.list) || [];
        this.table.list = this.table.list.map((x) => ({
          ...x,
          parse_status: x.parse_status || (x.is_chunked ? "completed" : "unknown"),
          parse_progress: typeof x.parse_progress === "number" ? x.parse_progress : x.is_chunked ? 1 : 0,
        }));
        this.table.total = (res.data && res.data.total) || 0;
      } catch (_) {
        this.table.list = [];
        this.table.total = 0;
      } finally {
        this.querying = false;
        if (this.pendingQuery) {
          this.pendingQuery = false;
          this.search();
        }
      }
    },
    openProgressStream() {
      this.closeProgressStream();
      try {
        const es = new EventSource("/api/knowledge/parse-progress/stream");
        es.addEventListener("progress", (evt) => {
          try {
            const payload = JSON.parse(evt.data || "{}");
            this.applyProgressUpdates(payload.tasks || []);
          } catch (_) {}
        });
        es.onerror = () => {};
        this.progressStream = es;
      } catch (_) {}
    },
    closeProgressStream() {
      if (this.progressStream) {
        this.progressStream.close();
        this.progressStream = null;
      }
    },
    applyProgressUpdates(tasks) {
      if (!Array.isArray(tasks) || !tasks.length) return;
      const byDoc = {};
      tasks.forEach((t) => {
        if (t && t.doc_id) byDoc[t.doc_id] = t;
      });
      let shouldRefresh = false;
      this.table.list = this.table.list.map((row) => {
        const t = byDoc[row.doc_id];
        if (!t) return row;
        const prevStatus = row.parse_status || (row.is_chunked ? "completed" : "unknown");
        const nextStatus = t.status || prevStatus;
        const next = {
          ...row,
          parse_status: nextStatus,
          parse_progress: typeof t.progress === "number" ? t.progress : row.parse_progress,
        };
        if (nextStatus === "completed") {
          next.is_chunked = true;
          if (typeof t.chunk_size === "number" && t.chunk_size >= 0) {
            next.chunk_size = t.chunk_size;
          }
          if (prevStatus !== "completed") {
            shouldRefresh = true;
          }
        }
        if (nextStatus === "failed" && prevStatus !== "failed") {
          shouldRefresh = true;
        }
        return next;
      });
      if (shouldRefresh) {
        this.search();
      }
    },
    buildGroupedFromHits(hits) {
      const groupMap = {};
      (hits || []).forEach((h) => {
        const docId = h.doc_id || "";
        if (!docId) return;
        if (!groupMap[docId]) {
          groupMap[docId] = {
            doc_id: docId,
            doc_summary: h.doc_summary || "",
            doc_keywords: h.doc_keywords || [],
            matched_hits: [],
            related_chunks: h.related_chunks || [],
          };
        }
        groupMap[docId].matched_hits.push({ chunk_id: h.chunk_id, item_type: h.item_type, score: h.score, summary: h.summary });
        if ((!groupMap[docId].related_chunks || !groupMap[docId].related_chunks.length) && h.related_chunks) {
          groupMap[docId].related_chunks = h.related_chunks;
        }
      });
      return Object.values(groupMap);
    },
    async doSemantic() {
      if (!this.semantic.query) {
        this.$message.warning("请输入检索问题");
        return;
      }
      this.semantic.loading = true;
      try {
        const res = await semanticQuery({ query: this.semantic.query, top_k: 10, min_score: 0.6, classification: this.filters.classification || "" });
        const data = (res && res.data) || {};
        const list = Array.isArray(data.list) ? data.list : Array.isArray(data.hits) ? data.hits : [];
        const grouped = Array.isArray(data.grouped_docs) ? data.grouped_docs : this.buildGroupedFromHits(list);
        this.semantic.hits = list;
        this.semantic.grouped_docs = grouped;
      } catch (_) {
        this.semantic.hits = [];
        this.semantic.grouped_docs = [];
      } finally {
        this.semantic.loading = false;
      }
    },
    editRow(row) {
      this.edit = { visible: true, doc_id: row.doc_id, file_name: row.file_name };
    },
    async saveEdit() {
      try {
        await updateKnowledge(this.edit.doc_id, { file_name: this.edit.file_name });
        this.$message.success("保存成功");
        this.edit.visible = false;
        this.search();
      } catch (_) {}
    },
    async removeRow(row) {
      try {
        await this.$confirm(`确认删除 ${row.file_name} ?`, "提示", { type: "warning" });
        await deleteKnowledge(row.doc_id);
        this.$message.success("删除成功");
        this.search();
      } catch (_) {}
    },
    async triggerParse(row) {
      const docId = (row && row.doc_id) || "";
      if (!docId) return;
      try {
        await parseKnowledge(docId);
        this.$message.success("已提交解析任务");
        this.table.list = this.table.list.map((x) => {
          if (x.doc_id !== docId) return x;
          return { ...x, parse_status: "pending", parse_progress: 0 };
        });
      } catch (e) {
        const msg = (e && e.response && e.response.data && e.response.data.message) || e.message || "提交解析失败";
        this.$message.error(msg);
      }
    },
  },
};
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1f2d3d;
}

.page-desc {
  margin-top: 6px;
  color: #5f6f81;
  font-size: 13px;
}

.header-actions {
  display: flex;
  align-items: center;
}

.hidden-upload-input {
  display: none;
}

.doc-card-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 12px;
}

.doc-card {
  border-radius: 10px;
}

.doc-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.doc-id {
  font-weight: 600;
  color: #303133;
}

.doc-summary,
.doc-keywords {
  margin-bottom: 8px;
  line-height: 1.6;
}

.label {
  color: #606266;
  font-weight: 600;
}

.kw-tag {
  margin-right: 6px;
  margin-bottom: 6px;
}

.block-title {
  margin-top: 8px;
  margin-bottom: 6px;
  color: #303133;
  font-weight: 600;
}

.hit-row,
.related-row {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
  background: #fafafa;
}

.hit-meta,
.related-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
  color: #606266;
  font-size: 12px;
}

.hit-summary,
.related-summary,
.related-text {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
}

.related-text {
  color: #606266;
  margin-top: 4px;
}

.placeholder {
  color: #909399;
  font-size: 13px;
}

.related-collapse {
  margin-top: 10px;
}
</style>
