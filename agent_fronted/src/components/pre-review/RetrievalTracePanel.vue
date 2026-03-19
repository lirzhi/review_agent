<template>
  <div v-if="detail" class="block">
    <div class="title">检索轨迹</div>
    <div class="list-item">命中反馈样本数: {{ metricNumber(detail.metrics.evaluated_feedback_count) }}</div>
    <div class="list-item">检索 Precision / Recall / F1: {{ metricPercent(detail.metrics.precision) }} / {{ metricPercent(detail.metrics.recall) }} / {{ metricPercent(detail.metrics.f1) }}</div>

    <div class="subtitle">来源分布</div>
    <div v-if="sourceEntries.length">
      <div v-for="item in sourceEntries" :key="item.key" class="list-item">{{ item.label }}: {{ metricNumber(item.count) }}</div>
    </div>
    <div v-else class="empty">暂无来源分布数据。</div>

    <div class="subtitle">错误拆解</div>
    <div v-if="errorEntries.length">
      <div v-for="item in errorEntries" :key="item.key" class="issue-card">
        <div class="issue-title">{{ item.label }}</div>
        <div class="muted">次数: {{ metricNumber(item.count) }}</div>
      </div>
    </div>
    <div v-else class="empty">暂无检索错误拆解数据。</div>
  </div>
</template>

<script>
const ERROR_LABELS = {
  query_miss: "查询漏召回",
  retrieval_scope_error: "检索范围错误",
  retrieval_ranking_error: "检索排序错误",
  historical_experience_missing: "历史经验缺失",
  section_fact_extraction_error: "章节事实抽取错误",
  focus_point_miss: "关注点漏检",
  evidence_interpretation_error: "证据解释错误",
  over_inference: "过度推断",
  under_identification: "识别不足",
  wrong_severity: "风险等级错误",
  wording_not_actionable: "表述不可执行",
  missing_regulatory_basis: "缺少法规依据",
  unhelpful_question_to_applicant: "问题对申请人无帮助",
};

export default {
  name: "RetrievalTracePanel",
  props: {
    detail: {
      type: Object,
      default: () => ({ metrics: {}, source_breakdown: {}, error_breakdown: {} }),
    },
    metricPercent: {
      type: Function,
      required: true,
    },
    metricNumber: {
      type: Function,
      required: true,
    },
  },
  computed: {
    sourceEntries() {
      const sourceBreakdown = this.detail && this.detail.source_breakdown && typeof this.detail.source_breakdown === "object"
        ? this.detail.source_breakdown
        : {};
      return Object.keys(sourceBreakdown)
        .map((key) => ({ key, label: key, count: sourceBreakdown[key] }))
        .sort((a, b) => Number(b.count || 0) - Number(a.count || 0));
    },
    errorEntries() {
      const errorBreakdown = this.detail && this.detail.error_breakdown && typeof this.detail.error_breakdown === "object"
        ? this.detail.error_breakdown
        : {};
      return Object.keys(errorBreakdown)
        .map((key) => ({
          key,
          label: ERROR_LABELS[key] || key,
          count: errorBreakdown[key],
        }))
        .sort((a, b) => Number(b.count || 0) - Number(a.count || 0));
    },
  },
};
</script>

<style scoped>
.block {
  border: 1px solid #eef1f6;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}
.title,
.issue-title {
  font-size: 14px;
  font-weight: 600;
  color: #2d3648;
}
.subtitle {
  margin: 12px 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: #2d3648;
}
.list-item,
.muted,
.empty {
  color: #4b5565;
  font-size: 12px;
  line-height: 1.6;
}
.issue-card {
  margin-top: 8px;
  border: 1px solid #e6ebf2;
  border-radius: 8px;
  padding: 10px;
}
</style>
