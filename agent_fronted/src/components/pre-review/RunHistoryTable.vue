<template>
  <div>
    <div class="toolbar">
      <span class="label">反馈回路筛选</span>
      <el-radio-group v-model="feedbackLoopFilter" size="mini">
        <el-radio-button label="all">全部</el-radio-button>
        <el-radio-button label="feedback_optimize">开启</el-radio-button>
        <el-radio-button label="feedback_only">关闭</el-radio-button>
      </el-radio-group>
    </div>

    <el-table
      v-if="filteredRuns.length"
      :data="filteredRuns"
      size="mini"
      border
      height="220"
      highlight-current-row
      @current-change="$emit('select-run', $event)"
    >
      <el-table-column prop="version_no" label="版本" width="64" />
      <el-table-column prop="create_time" label="时间" min-width="132" />
      <el-table-column label="反馈回路" width="92">
        <template slot-scope="{ row }">{{ row.feedback_loop_mode === 'feedback_only' ? '关闭' : '开启' }}</template>
      </el-table-column>
      <el-table-column label="审评 P" width="84">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).review || {}).precision)) }}</template>
      </el-table-column>
      <el-table-column label="审评 R" width="84">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).review || {}).recall)) }}</template>
      </el-table-column>
      <el-table-column label="审评 F1" width="84">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).review || {}).f1)) }}</template>
      </el-table-column>
      <el-table-column label="检索 P" width="84">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).retrieval || {}).precision)) }}</template>
      </el-table-column>
      <el-table-column label="检索 R" width="84">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).retrieval || {}).recall)) }}</template>
      </el-table-column>
      <el-table-column label="检索 F1" width="84">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).retrieval || {}).f1)) }}</template>
      </el-table-column>
      <el-table-column label="反馈采纳" width="92">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).feedback || {}).feedback_acceptance_rate)) }}</template>
      </el-table-column>
      <el-table-column label="人工修改" width="92">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).feedback || {}).manual_modification_rate)) }}</template>
      </el-table-column>
      <el-table-column label="误报下降" width="92">
        <template slot-scope="{ row }">{{ metricPercent((((row.metrics || {}).trajectory || {}).false_positive_reduction_rate)) }}</template>
      </el-table-column>
    </el-table>
    <div v-else class="empty">当前筛选条件下暂无预审运行记录。</div>
  </div>
</template>

<script>
export default {
  name: "RunHistoryTable",
  props: {
    runs: {
      type: Array,
      default: () => [],
    },
    metricPercent: {
      type: Function,
      required: true,
    },
  },
  data() {
    return {
      feedbackLoopFilter: "all",
    };
  },
  computed: {
    filteredRuns() {
      if (this.feedbackLoopFilter === "all") {
        return this.runs;
      }
      return (this.runs || []).filter(
        (row) => String((row && row.feedback_loop_mode) || "feedback_optimize") === this.feedbackLoopFilter
      );
    },
  },
};
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.label {
  color: #5a667a;
  font-size: 12px;
}
.empty {
  color: #8a94a6;
  font-size: 12px;
  line-height: 1.6;
}
</style>
