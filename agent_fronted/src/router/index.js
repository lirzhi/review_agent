import Vue from "vue";
import Router from "vue-router";

import MainLayout from "@/layout/MainLayout.vue";
import Dashboard from "@/views/Dashboard.vue";
import GuidelineManage from "@/views/GuidelineManage.vue";
import PolicyManage from "@/views/PolicyManage.vue";
import LawManage from "@/views/LawManage.vue";
import ICHManage from "@/views/ICHManage.vue";
import PharmacopeiaManage from "@/views/PharmacopeiaManage.vue";
import HistoryExperienceManage from "@/views/HistoryExperienceManage.vue";
import CommonIssueManage from "@/views/CommonIssueManage.vue";
import ReviewCriteriaManage from "@/views/ReviewCriteriaManage.vue";
import PreReviewManage from "@/views/PreReviewManage.vue";
import PreReviewSession from "@/views/PreReviewSession.vue";

Vue.use(Router);

export default new Router({
  mode: "hash",
  routes: [
    {
      path: "/",
      component: MainLayout,
      redirect: "/dashboard",
      children: [
        {
          path: "dashboard",
          name: "dashboard",
          component: Dashboard,
          meta: { title: "仪表盘" },
        },
        {
          path: "knowledge",
          redirect: "/knowledge/guideline",
        },
        {
          path: "knowledge/guideline",
          name: "knowledge-guideline",
          component: GuidelineManage,
          meta: { title: "知识库管理 - 指导原则" },
        },
        {
          path: "knowledge/policy",
          name: "knowledge-policy",
          component: PolicyManage,
          meta: { title: "知识库管理 - 制度规范" },
        },
        {
          path: "knowledge/law",
          name: "knowledge-law",
          component: LawManage,
          meta: { title: "知识库管理 - 法律法规" },
        },
        {
          path: "knowledge/ich",
          name: "knowledge-ich",
          component: ICHManage,
          meta: { title: "知识库管理 - ICH" },
        },
        {
          path: "knowledge/pharmacopeia",
          name: "knowledge-pharmacopeia",
          component: PharmacopeiaManage,
          meta: { title: "知识库管理 - 药典数据" },
        },
        {
          path: "knowledge/experience",
          name: "knowledge-experience",
          component: HistoryExperienceManage,
          meta: { title: "知识库管理 - 历史经验" },
        },
        {
          path: "knowledge/common-issue",
          name: "knowledge-common-issue",
          component: CommonIssueManage,
          meta: { title: "知识库管理 - 共性问题" },
        },
        {
          path: "knowledge/review-rule",
          name: "knowledge-review-rule",
          component: ReviewCriteriaManage,
          meta: { title: "知识库管理 - 审评准则" },
        },
        {
          path: "pre-review",
          name: "pre-review",
          component: PreReviewManage,
          meta: { title: "预审项目管理" },
        },
        {
          path: "pre-review/session/:projectId",
          name: "pre-review-session",
          component: PreReviewSession,
          meta: { title: "预审会话" },
        },
      ],
    },
  ],
});
