<template>
  <div v-if="metrics" class="block">
    <div class="title">运行指标</div>
    <div class="list-item">审评 Accuracy / Recall / F1: {{ metricPercent(metrics.review.accuracy) }} / {{ metricPercent(metrics.review.recall) }} / {{ metricPercent(metrics.review.f1) }}</div>
    <div class="list-item">检索 Accuracy / Recall / F1: {{ metricPercent(metrics.retrieval.accuracy) }} / {{ metricPercent(metrics.retrieval.recall) }} / {{ metricPercent(metrics.retrieval.f1) }}</div>
    <div class="list-item">反馈采纳率: {{ metricPercent(metrics.feedback.feedback_acceptance_rate) }}</div>
    <div class="list-item">人工修改率: {{ metricPercent(metrics.feedback.manual_modification_rate) }}</div>
    <div class="list-item">误报下降率: {{ metricPercent(metrics.trajectory.false_positive_reduction_rate) }}</div>
    <div class="list-item">仅反馈 / 优化回路: {{ metricNumber(metrics.feedback.feedback_only_count) }} / {{ metricNumber(metrics.feedback.feedback_optimize_count) }}</div>
    <div class="list-item">Optimize Success / Failed: {{ metricNumber(metrics.feedback.feedback_optimize_success_count) }} / {{ metricNumber(metrics.feedback.feedback_optimize_failed_count) }}</div>
    <div class="list-item">Candidate Register Success / Failed: {{ metricNumber(metrics.feedback.candidate_register_success_count) }} / {{ metricNumber(metrics.feedback.candidate_register_failed_count) }}</div>
    <div class="list-item">Replay Passed / Failed: {{ metricNumber(metrics.feedback.replay_pass_count) }} / {{ metricNumber(metrics.feedback.replay_failed_count) }}</div>
  </div>
</template>

<script>
export default {
  name: "RunMetricsPanel",
  props: {
    metrics: {
      type: Object,
      default: () => ({ review: {}, retrieval: {}, feedback: {}, trajectory: {} }),
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
};
</script>

<style scoped>
.block {
  border: 1px solid #eef1f6;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}
.title {
  font-size: 14px;
  font-weight: 600;
  color: #2d3648;
}
.list-item {
  margin-top: 8px;
  color: #4b5565;
  font-size: 12px;
  line-height: 1.6;
}
</style>
