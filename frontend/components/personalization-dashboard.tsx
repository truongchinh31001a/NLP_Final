"use client";

import {
  ArrowLeftOutlined,
  BulbOutlined,
  FireOutlined,
  RadarChartOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Empty,
  Progress,
  Row,
  Col,
  Skeleton,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getPersonalizationSnapshot } from "@/lib/api";
import type {
  PersonalizationErrorStat,
  PersonalizationSnapshot,
  PersonalizationSkillMastery,
  PersonalizationSubtopicStat,
  PersonalizationTopicStat,
} from "@/lib/types";

const USER_ID = "demo-user";

export function PersonalizationDashboard() {
  const [snapshot, setSnapshot] = useState<PersonalizationSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSnapshot() {
      try {
        const data = await getPersonalizationSnapshot(USER_ID);
        if (isMounted) {
          setSnapshot(data);
          setError(null);
        }
      } catch {
        if (isMounted) {
          setError("Khong tai duoc du lieu ca nhan hoa tu backend.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadSnapshot();

    return () => {
      isMounted = false;
    };
  }, []);

  const summary = useMemo(() => {
    if (!snapshot) {
      return {
        totalAttempts: 0,
        weightedAccuracy: 0,
        averageMastery: 0,
        topWeakSkill: null as PersonalizationSkillMastery | null,
        topWeakSubtopic: null as PersonalizationSubtopicStat | null,
        topError: null as PersonalizationErrorStat | null,
      };
    }

    const totalAttempts = snapshot.topicStats.reduce(
      (sum, item) => sum + item.attemptsCount,
      0,
    );
    const totalCorrect = snapshot.topicStats.reduce(
      (sum, item) => sum + item.correctCount,
      0,
    );

    return {
      totalAttempts,
      weightedAccuracy:
        totalAttempts > 0 ? totalCorrect / Math.max(totalAttempts, 1) : 0,
      averageMastery: snapshot.skillMastery.length
        ? snapshot.skillMastery.reduce(
            (sum, item) => sum + item.masteryProbability,
            0,
          ) / snapshot.skillMastery.length
        : 0,
      topWeakSkill: snapshot.skillMastery[0] ?? null,
      topWeakSubtopic: snapshot.subtopicStats[0] ?? null,
      topError: snapshot.errorStats[0] ?? null,
    };
  }, [snapshot]);

  const topicColumns: ColumnsType<PersonalizationTopicStat> = [
    {
      title: "Topic",
      dataIndex: "label",
      key: "label",
      render: (label, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{label}</Typography.Text>
          <Typography.Text type="secondary">{row.status ?? "new"}</Typography.Text>
        </Space>
      ),
    },
    {
      title: "Accuracy",
      dataIndex: "accuracy",
      key: "accuracy",
      render: (accuracy) => (
        <Progress
          percent={toPercent(Number(accuracy))}
          size="small"
          strokeColor="#147447"
        />
      ),
    },
    {
      title: "Attempts",
      dataIndex: "attemptsCount",
      key: "attemptsCount",
      width: 110,
    },
    {
      title: "Weakness",
      dataIndex: "weaknessScore",
      key: "weaknessScore",
      render: (score) => <Tag color={weaknessColor(Number(score))}>{toPercent(Number(score))}%</Tag>,
      width: 120,
    },
  ];

  const subtopicColumns: ColumnsType<PersonalizationSubtopicStat> = [
    {
      title: "Subtopic",
      dataIndex: "label",
      key: "label",
      render: (label, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{label}</Typography.Text>
          <Typography.Text type="secondary">{formatCode(row.topic)}</Typography.Text>
        </Space>
      ),
    },
    {
      title: "Mastery",
      dataIndex: "masteryScore",
      key: "masteryScore",
      render: (score) => (
        <Progress
          percent={toPercent(Number(score))}
          size="small"
          strokeColor="#2454a6"
        />
      ),
    },
    {
      title: "Accuracy",
      dataIndex: "accuracy",
      key: "accuracy",
      render: (accuracy) => `${toPercent(Number(accuracy))}%`,
      width: 100,
    },
    {
      title: "Attempts",
      dataIndex: "attemptsCount",
      key: "attemptsCount",
      width: 100,
    },
  ];

  const errorColumns: ColumnsType<PersonalizationErrorStat> = [
    {
      title: "Error Pattern",
      dataIndex: "label",
      key: "label",
      render: (label, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{label}</Typography.Text>
          <Typography.Text type="secondary">{formatCode(row.topic)}</Typography.Text>
        </Space>
      ),
    },
    {
      title: "Error Rate",
      dataIndex: "errorRate",
      key: "errorRate",
      render: (rate) => (
        <Progress
          percent={toPercent(Number(rate))}
          size="small"
          strokeColor="#b42318"
        />
      ),
    },
    {
      title: "Incorrect",
      dataIndex: "incorrectCount",
      key: "incorrectCount",
      width: 100,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status) => <Tag color="red">{status ?? "watch"}</Tag>,
      width: 130,
    },
  ];

  const skillColumns: ColumnsType<PersonalizationSkillMastery> = [
    {
      title: "Skill",
      dataIndex: "label",
      key: "label",
      render: (label, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{label}</Typography.Text>
          <Typography.Text type="secondary">
            {formatCode(row.topic)} - {row.cefr ?? "CEFR n/a"}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: "Mastery",
      dataIndex: "masteryProbability",
      key: "masteryProbability",
      render: (mastery) => (
        <Progress
          percent={toPercent(Number(mastery))}
          size="small"
          strokeColor="#2454a6"
        />
      ),
    },
    {
      title: "Confidence",
      dataIndex: "confidence",
      key: "confidence",
      render: (confidence) => `${toPercent(Number(confidence))}%`,
      width: 110,
    },
    {
      title: "Attempts",
      dataIndex: "attemptsCount",
      key: "attemptsCount",
      width: 100,
    },
    {
      title: "Next Review",
      dataIndex: "nextReviewAt",
      key: "nextReviewAt",
      render: (value) => formatReviewDate(value),
      width: 150,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status, row) => (
        <Tag color={weaknessColor(row.weaknessScore)}>
          {status ?? "learning"}
        </Tag>
      ),
      width: 120,
    },
  ];

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#2454a6",
          borderRadius: 10,
          fontFamily: "var(--font-body), sans-serif",
        },
      }}
    >
      <main className="personalization-shell">
        <header className="personalization-hero">
          <div>
            <p className="eyebrow">Learner Intelligence</p>
            <Typography.Title level={1}>Dashboard ca nhan hoa</Typography.Title>
            <Typography.Paragraph>
              Theo doi mastery, loi sai lap lai va ly do he thong chon bai
              luyen tiep theo cho nguoi hoc.
            </Typography.Paragraph>
          </div>
          <Space wrap>
            <Link href="/debug/chroma">
              <Button size="large">Xem Chroma</Button>
            </Link>
            <Link href="/">
              <Button icon={<ArrowLeftOutlined />} size="large">
                Quay lai chatbot
              </Button>
            </Link>
          </Space>
        </header>

        {isLoading ? (
          <Card>
            <Skeleton active paragraph={{ rows: 8 }} />
          </Card>
        ) : null}

        {!isLoading && error ? (
          <Alert
            message="Backend chua san sang"
            description={error}
            showIcon
            type="error"
          />
        ) : null}

        {!isLoading && snapshot ? (
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <Row gutter={[16, 16]}>
              <Col lg={6} sm={12} xs={24}>
                <Card className="metric-card">
                  <Statistic
                    prefix={<UserOutlined />}
                    title="Learner"
                    value={snapshot.userId}
                  />
                  <Tag color="blue">{snapshot.level}</Tag>
                </Card>
              </Col>
              <Col lg={6} sm={12} xs={24}>
                <Card className="metric-card">
                  <Statistic
                    prefix={<RadarChartOutlined />}
                    title="Total Attempts"
                    value={summary.totalAttempts}
                  />
                  <Typography.Text type="secondary">
                    Du lieu tu cac session da nop bai
                  </Typography.Text>
                </Card>
              </Col>
              <Col lg={6} sm={12} xs={24}>
                <Card className="metric-card">
                  <Statistic
                    title="Overall Accuracy"
                    value={toPercent(summary.weightedAccuracy)}
                    suffix="%"
                  />
                  <Progress
                    percent={toPercent(summary.weightedAccuracy)}
                    size="small"
                    strokeColor="#147447"
                  />
                  <Typography.Text type="secondary">
                    Avg mastery {toPercent(summary.averageMastery)}%
                  </Typography.Text>
                </Card>
              </Col>
              <Col lg={6} sm={12} xs={24}>
                <Card className="metric-card">
                  <Statistic
                    prefix={<FireOutlined />}
                    title="Top Weakness"
                    value={
                      summary.topWeakSkill?.label ??
                      summary.topWeakSubtopic?.label ??
                      "No data"
                    }
                    valueStyle={{ fontSize: 18 }}
                  />
                  {summary.topError ? (
                    <Tag color="red">{summary.topError.label}</Tag>
                  ) : null}
                </Card>
              </Col>
            </Row>

            <Card
              className="next-plan-card"
              title={
                <Space>
                  <BulbOutlined />
                  Next Personalized Plan
                </Space>
              }
            >
              <Row gutter={[18, 18]} align="middle">
                <Col lg={14} xs={24}>
                  <Typography.Title level={3}>
                    {formatCode(snapshot.nextPlan.topic)} -{" "}
                    {snapshot.nextPlan.difficulty}
                  </Typography.Title>
                  <Typography.Paragraph>
                    {snapshot.nextPlan.focusReason}
                  </Typography.Paragraph>
                  <Space wrap>
                    <Tag color="blue">{snapshot.nextPlan.exerciseType}</Tag>
                    <Tag color="geekblue">
                      {snapshot.nextPlan.numQuestions} cau
                    </Tag>
                    {snapshot.nextPlan.targetSubtopic ? (
                      <Tag color="orange">
                        {formatCode(snapshot.nextPlan.targetSubtopic)}
                      </Tag>
                    ) : null}
                    {snapshot.nextPlan.targetErrorTag ? (
                      <Tag color="red">
                        <WarningOutlined />{" "}
                        {formatCode(snapshot.nextPlan.targetErrorTag)}
                      </Tag>
                    ) : null}
                    {snapshot.nextPlan.targetSkillId ? (
                      <Tag color="purple">
                        {formatCode(snapshot.nextPlan.targetSkillId)}
                      </Tag>
                    ) : null}
                  </Space>
                </Col>
                <Col lg={10} xs={24}>
                  <Alert
                    message="Learner summary dua vao planner"
                    description={
                      snapshot.nextPlan.learnerSummary ||
                      "Chua co lich su hoc tap du de tao summary."
                    }
                    showIcon
                    type="info"
                  />
                </Col>
              </Row>
            </Card>

            {summary.totalAttempts === 0 ? (
              <Card>
                <Empty
                  description="Chua co du lieu ca nhan hoa. Hay tao bai, nop dap an, roi quay lai dashboard nay."
                />
              </Card>
            ) : (
              <Row gutter={[16, 16]}>
                <Col span={24}>
                  <Card title="Skill Mastery (BKT)">
                    <Table
                      columns={skillColumns}
                      dataSource={snapshot.skillMastery}
                      pagination={false}
                      rowKey="code"
                      size="middle"
                    />
                  </Card>
                </Col>
                <Col lg={12} xs={24}>
                  <Card title="Weak Subtopics va Mastery">
                    <Table
                      columns={subtopicColumns}
                      dataSource={snapshot.subtopicStats}
                      pagination={false}
                      rowKey="code"
                      size="middle"
                    />
                  </Card>
                </Col>
                <Col lg={12} xs={24}>
                  <Card title="Frequent Error Patterns">
                    <Table
                      columns={errorColumns}
                      dataSource={snapshot.errorStats}
                      pagination={false}
                      rowKey="code"
                      size="middle"
                    />
                  </Card>
                </Col>
                <Col span={24}>
                  <Card title="Topic Level Memory">
                    <Table
                      columns={topicColumns}
                      dataSource={snapshot.topicStats}
                      pagination={false}
                      rowKey="code"
                      size="middle"
                    />
                  </Card>
                </Col>
              </Row>
            )}
          </Space>
        ) : null}
      </main>
    </ConfigProvider>
  );
}

function toPercent(value: number) {
  return Math.round(Math.max(0, Math.min(value, 1)) * 100);
}

function weaknessColor(score: number) {
  if (score >= 0.7) {
    return "red";
  }
  if (score >= 0.4) {
    return "orange";
  }
  return "green";
}

function formatCode(value: string) {
  return value.replaceAll("_", " ");
}

function formatReviewDate(value?: string | null) {
  if (!value) {
    return "Not scheduled";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}
