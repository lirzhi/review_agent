<template>
  <div v-if="review" class="block grow">
    <div class="title">章节标准输出</div>
    <div class="muted">
      {{ review.section_name || currentBrowseSectionLabel }}
      <span v-if="review.section_id">（{{ review.section_id }}）</span>
    </div>

    <div class="summary">
      <div><strong>预审结论:</strong> {{ reviewConclusionLabel(review.pre_review_conclusion || review.conclusion) }}</div>
      <div v-if="review.section_summary"><strong>章节摘要:</strong> {{ review.section_summary }}</div>
      <div v-else-if="review.summary"><strong>章节摘要:</strong> {{ review.summary }}</div>
    </div>

    <div class="subtitle">已支持要点</div>
    <div v-if="normalizedSupportedPoints.length">
      <div v-for="(item, index) in normalizedSupportedPoints" :key="'supported-' + index" class="list-item">{{ index + 1 }}. {{ item }}</div>
    </div>
    <div v-else class="empty">暂无已支持要点。</div>

    <div class="subtitle">不支持要点</div>
    <div v-if="normalizedUnsupportedPoints.length">
      <div v-for="(item, index) in normalizedUnsupportedPoints" :key="'unsupported-' + index" class="issue-card">
        <div class="issue-title">问题 {{ index + 1 }}</div>
        <div class="muted">{{ item }}</div>
      </div>
    </div>
    <div v-else class="empty">暂无不支持要点。</div>

    <div class="subtitle">缺失要点</div>
    <div v-if="normalizedMissingPoints.length">
      <div v-for="(item, index) in normalizedMissingPoints" :key="'missing-' + index" class="list-item">{{ index + 1 }}. {{ item }}</div>
    </div>
    <div v-else class="empty">暂无缺失要点。</div>

    <div class="subtitle">风险提示</div>
    <div v-if="normalizedRiskPoints.length">
      <div v-for="(item, index) in normalizedRiskPoints" :key="'risk-' + index" class="list-item">{{ index + 1 }}. {{ item }}</div>
    </div>
    <div v-else class="empty">暂无风险提示。</div>

    <div class="subtitle">问题清单</div>
    <div v-if="normalizedQuestions.length">
      <div v-for="(item, index) in normalizedQuestions" :key="'question-' + index" class="issue-card">
        <div class="issue-title">{{ item.issue || `问题 ${index + 1}` }}</div>
        <div class="muted"><strong>依据:</strong> {{ item.basis || '-' }}</div>
        <div class="muted"><strong>建议补充:</strong> {{ item.requested_action || '-' }}</div>
      </div>
    </div>
    <div v-else class="empty">暂无问题清单。</div>

    <div class="subtitle">证据引用</div>
    <div v-if="normalizedEvidenceRefs.length">
      <div v-for="(item, index) in normalizedEvidenceRefs" :key="'evidence-' + index" class="list-item">{{ index + 1 }}. {{ item }}</div>
    </div>
    <div v-else class="empty">暂无证据引用。</div>

    <div class="subtitle">检索证据</div>
    <div v-if="selectedEvidenceGroups.length">
      <div v-for="group in selectedEvidenceGroups" :key="group.source" class="nested-block">
        <div class="issue-title">{{ group.source }}</div>
        <div v-for="(item, index) in group.items" :key="group.source + '-' + index" class="issue-card">
          <div class="muted"><strong>标题:</strong> {{ item.title || '-' }}</div>
          <div class="muted"><strong>摘要:</strong> {{ item.doc_summary || item.content || '-' }}</div>
          <div class="muted"><strong>路径:</strong> {{ item.section_path_text || item.section_name || '-' }}</div>
          <div class="muted"><strong>分数:</strong> {{ item.score != null ? item.score : '-' }}</div>
        </div>
      </div>
    </div>
    <div v-else class="empty">暂无检索证据。</div>

    <div class="subtitle">命中规则</div>
    <div v-if="selectedPromptRules.planner.length || selectedPromptRules.reviewer.length">
      <div v-if="selectedPromptRules.planner.length" class="nested-block">
        <div class="issue-title">Planner</div>
        <div v-for="(item, index) in selectedPromptRules.planner" :key="'planner-rule-' + index" class="issue-card">
          <div class="muted"><strong>规则:</strong> {{ item.rule_name || item.rule_code || '-' }}</div>
          <div class="muted"><strong>模板:</strong> {{ item.template_name || '-' }}</div>
          <div class="muted"><strong>优先级:</strong> {{ item.priority != null ? item.priority : '-' }}</div>
          <div class="muted"><strong>范围:</strong> {{ item.scope_type || '-' }}</div>
          <div class="muted"><strong>来源:</strong> {{ item.source_type || '-' }}</div>
        </div>
      </div>
      <div v-if="selectedPromptRules.reviewer.length" class="nested-block">
        <div class="issue-title">Reviewer</div>
        <div v-for="(item, index) in selectedPromptRules.reviewer" :key="'reviewer-rule-' + index" class="issue-card">
          <div class="muted"><strong>规则:</strong> {{ item.rule_name || item.rule_code || '-' }}</div>
          <div class="muted"><strong>模板:</strong> {{ item.template_name || '-' }}</div>
          <div class="muted"><strong>优先级:</strong> {{ item.priority != null ? item.priority : '-' }}</div>
          <div class="muted"><strong>范围:</strong> {{ item.scope_type || '-' }}</div>
          <div class="muted"><strong>来源:</strong> {{ item.source_type || '-' }}</div>
        </div>
      </div>
    </div>
    <div v-else class="empty">当前章节未显示命中的项目规则。</div>

    <div class="subtitle">反馈</div>
    <el-select v-model="feedbackForm.decision" size="small" style="width: 180px">
      <el-option label="认可" value="valid" />
      <el-option label="误报" value="false_positive" />
      <el-option label="漏报" value="missed" />
    </el-select>
    <div style="margin-top: 12px">
      <div class="muted" style="margin-bottom: 6px;">当前运行反馈回路：{{ feedbackLoopMode === "feedback_only" ? "关闭" : "开启" }}</div>
      <el-switch
        v-model="feedbackForm.enableOptimize"
        active-text="反馈优化回路"
        inactive-text="仅记录反馈"
        :disabled="feedbackLoopLocked"
      />
    </div>
    <el-input
      v-model="feedbackForm.feedback_text"
      type="textarea"
      :rows="4"
      placeholder="填写本章节反馈意见，作为后续优化信号"
      style="margin-top: 12px"
    />
    <div class="actions" style="margin-top: 12px">
      <el-button
        size="mini"
        type="primary"
        :disabled="!selectedRun || !review"
        :loading="submittingFeedback"
        @click="$emit('submit-feedback')"
      >
        {{ feedbackForm.enableOptimize ? '提交反馈并优化' : '仅提交反馈' }}
      </el-button>
    </div>

    <div v-if="feedbackForm.enableOptimize && (feedbackOptimizeResult.feedback_key || feedbackOptimizeResult.feedback_optimize_status)" class="block nested-block">
      <div class="title">反馈优化结果</div>
      <div class="muted">feedback_key: {{ feedbackOptimizeResult.feedback_key }}</div>
      <div class="muted"><strong>Optimize Status:</strong> {{ feedbackOptimizeResult.feedback_optimize_status || '-' }}</div>
      <div class="muted"><strong>Candidate Register:</strong> {{ feedbackOptimizeResult.candidate_register_status || '-' }}</div>
      <div class="muted"><strong>Replay Status:</strong> {{ feedbackOptimizeResult.replay_status || '-' }}</div>
      <div v-if="feedbackOptimizeResult.error_message" class="muted"><strong>Error:</strong> {{ feedbackOptimizeResult.error_message }}</div>
      <div class="subtitle">分析结果</div>
      <pre class="json-view">{{ formattedFeedbackAnalysis }}</pre>
      <div class="subtitle">当前 Patch 候选</div>
      <div v-if="currentPatchCandidates.length">
        <div v-for="(patch, index) in currentPatchCandidates" :key="'current-patch-' + index" class="issue-card">
          <div class="issue-title">{{ patch.patch_type || `patch_${index + 1}` }}</div>
          <div class="muted"><strong>目标 Agent:</strong> {{ patch.target_agent || '-' }}</div>
          <div class="muted"><strong>触发条件:</strong> {{ patch.trigger_condition || '-' }}</div>
          <div class="muted"><strong>Patch 内容:</strong> {{ patch.patch_content || '-' }}</div>
        </div>
      </div>
      <pre class="json-view">{{ formattedFeedbackPatch }}</pre>
    </div>

    <div class="block nested-block">
      <div class="title">章节历史 Patch 候选</div>
      <div v-if="historicalPatchCandidates.length">
        <div v-for="(patch, index) in historicalPatchCandidates" :key="patch.patch_id || 'history-patch-' + index" class="issue-card">
          <div class="issue-title">{{ patch.patch_type || `patch_${index + 1}` }}</div>
          <div class="muted"><strong>Run:</strong> {{ patch.run_id || '-' }}</div>
          <div class="muted"><strong>目标 Agent:</strong> {{ patch.target_agent || '-' }}</div>
          <div class="muted"><strong>状态 / 版本:</strong> {{ patch.status || '-' }} / {{ patch.version || '-' }}</div>
          <div class="muted"><strong>触发条件:</strong> {{ patch.trigger_condition || '-' }}</div>
          <div class="muted"><strong>Patch 内容:</strong> {{ patch.patch_content || '-' }}</div>
          <div class="muted"><strong>更新时间:</strong> {{ patch.update_time || patch.create_time || '-' }}</div>
        </div>
      </div>
      <div v-else class="empty">暂无该章节的历史 Patch 候选。</div>
    </div>
  </div>
</template>

<script>
export default {
  name: "SectionReviewPanel",
  props: {
    review: { type: Object, default: null },
    currentBrowseSectionLabel: { type: String, default: "" },
    normalizedSupportedPoints: { type: Array, default: () => [] },
    normalizedUnsupportedPoints: { type: Array, default: () => [] },
    normalizedMissingPoints: { type: Array, default: () => [] },
    normalizedRiskPoints: { type: Array, default: () => [] },
    normalizedQuestions: { type: Array, default: () => [] },
    normalizedEvidenceRefs: { type: Array, default: () => [] },
    selectedEvidenceGroups: { type: Array, default: () => [] },
    selectedPromptRules: {
      type: Object,
      default: () => ({ planner: [], reviewer: [] }),
    },
    feedbackForm: { type: Object, required: true },
    selectedRun: { type: Object, default: null },
    submittingFeedback: { type: Boolean, default: false },
    feedbackOptimizeResult: {
      type: Object,
      default: () => ({
        feedback_key: '',
        analysis_result: null,
        patch_result: null,
        feedback_optimize_status: '',
        candidate_register_status: '',
        replay_status: '',
        error_message: '',
      }),
    },
    currentPatchCandidates: { type: Array, default: () => [] },
    historicalPatchCandidates: { type: Array, default: () => [] },
    formattedFeedbackAnalysis: { type: String, default: '{}' },
    formattedFeedbackPatch: { type: String, default: '{}' },
    reviewConclusionLabel: { type: Function, required: true },
    feedbackLoopMode: { type: String, default: "feedback_optimize" },
    feedbackLoopLocked: { type: Boolean, default: false },
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
.grow {
  flex: 1;
  overflow: auto;
}
.nested-block {
  margin-top: 16px;
  background: #fafcff;
}
.title {
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
.summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #4b5565;
  margin-top: 8px;
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
.issue-title {
  font-weight: 600;
  color: #2d3648;
  margin-bottom: 6px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.json-view {
  margin: 0;
  padding: 10px;
  border: 1px solid #eef1f6;
  border-radius: 6px;
  background: #f7f9fc;
  color: #2d3648;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>


