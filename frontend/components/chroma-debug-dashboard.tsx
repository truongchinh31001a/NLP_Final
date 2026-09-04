"use client";

import {
  ArrowLeftOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  Empty,
  Row,
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

import { getChromaDebugSnapshot } from "@/lib/api";
import type { ChromaDebugChunk, ChromaDebugSnapshot } from "@/lib/types";

type CountRow = {
  name: string;
  count: number;
};

export function ChromaDebugDashboard() {
  const [snapshot, setSnapshot] = useState<ChromaDebugSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadSnapshot() {
    setIsLoading(true);
    try {
      const data = await getChromaDebugSnapshot();
      setSnapshot(data);
      setError(null);
    } catch {
      setError("Khong tai duoc thong tin Chroma tu backend.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadSnapshot();
  }, []);

  const topicRows = useMemo(
    () => toCountRows(snapshot?.topicCounts ?? {}),
    [snapshot],
  );
  const levelRows = useMemo(
    () => toCountRows(snapshot?.levelCounts ?? {}),
    [snapshot],
  );

  const countColumns: ColumnsType<CountRow> = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      render: (name) => <Typography.Text strong>{formatCode(String(name))}</Typography.Text>,
    },
    {
      title: "Chunks",
      dataIndex: "count",
      key: "count",
      width: 110,
      render: (count) => <Tag color="blue">{Number(count)}</Tag>,
    },
  ];

  const chunkColumns: ColumnsType<ChromaDebugChunk> = [
    {
      title: "Chunk",
      dataIndex: "chunkId",
      key: "chunkId",
      width: 210,
      render: (chunkId, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{chunkId}</Typography.Text>
          <Typography.Text type="secondary">{row.source ?? "unknown"}</Typography.Text>
        </Space>
      ),
    },
    {
      title: "Metadata",
      key: "metadata",
      width: 260,
      render: (_, row) => (
        <Space wrap>
          <Tag color="geekblue">{formatCode(row.topic)}</Tag>
          <Tag color="green">{row.level}</Tag>
          {row.skill ? <Tag>{row.skill}</Tag> : null}
          {row.subtopic ? <Tag color="purple">{formatCode(row.subtopic)}</Tag> : null}
        </Space>
      ),
    },
    {
      title: "Content Preview",
      dataIndex: "contentPreview",
      key: "contentPreview",
      render: (preview) => (
        <Typography.Paragraph className="debug-preview" ellipsis={{ rows: 3 }}>
          {preview}
        </Typography.Paragraph>
      ),
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
      <main className="personalization-shell debug-shell">
        <header className="personalization-hero debug-hero">
          <div>
            <p className="eyebrow">Vector Store Debug</p>
            <Typography.Title level={1}>Chroma knowledge store</Typography.Title>
            <Typography.Paragraph>
              Kiem tra collection, so chunk, metadata topic/level va mot vai chunk mau
              dang duoc luu trong Chroma.
            </Typography.Paragraph>
          </div>
          <Space wrap>
            <Button icon={<ReloadOutlined />} size="large" onClick={loadSnapshot}>
              Tai lai
            </Button>
            <Link href="/personalization">
              <Button size="large">Ca nhan hoa</Button>
            </Link>
            <Link href="/">
              <Button icon={<ArrowLeftOutlined />} size="large">
                Chatbot
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
          <Alert message="Backend chua san sang" description={error} showIcon type="error" />
        ) : null}

        {!isLoading && snapshot ? (
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <Alert
              message={snapshot.isAvailable ? "Chroma da co du lieu" : "Chroma dang rong"}
              description={snapshot.statusMessage}
              showIcon
              type={snapshot.isAvailable ? "success" : "warning"}
            />

            <Row gutter={[16, 16]}>
              <Col lg={6} sm={12} xs={24}>
                <Card className="metric-card">
                  <Statistic
                    prefix={<DatabaseOutlined />}
                    title="Collection"
                    value={snapshot.collectionName}
                  />
                  <Tag color={snapshot.usingChromaBackend ? "green" : "orange"}>
                    backend: {snapshot.configuredBackend}
                  </Tag>
                  <Tag color="blue">mode: {snapshot.retrievalMode}</Tag>
                  <Tag color="geekblue">embedding: {snapshot.embeddingBackend}</Tag>
                  <Tag color={snapshot.rerankerEnabled ? "green" : "default"}>
                    reranker: {snapshot.rerankerEnabled ? "on" : "off"}
                  </Tag>
                </Card>
              </Col>
              <Col lg={6} sm={12} xs={24}>
                <Card className="metric-card">
                  <Statistic
                    prefix={<DatabaseOutlined />}
                    title="Chroma chunks"
                    value={snapshot.totalChunks}
                  />
                  <Typography.Text type="secondary">
                    raw JSON: {snapshot.rawKnowledgeCount}
                  </Typography.Text>
                </Card>
              </Col>
              <Col lg={6} sm={12} xs={24}>
                <Card className="metric-card">
                  <Statistic title="Topics" value={topicRows.length} />
                  <Typography.Text type="secondary">
                    {snapshot.persistDirectory}
                  </Typography.Text>
                </Card>
              </Col>
              <Col lg={6} sm={12} xs={24}>
                <Card className="metric-card">
                  <Statistic title="Levels" value={levelRows.length} />
                  <Typography.Text type="secondary">
                    {snapshot.rawKnowledgePath}
                  </Typography.Text>
                </Card>
              </Col>
            </Row>

            {!snapshot.usingChromaBackend ? (
              <Alert
                message="Backend generate hien chua dung Chroma"
                description="Trang nay van inspect duoc Chroma persistent, nhung docker-compose hien dang de VECTOR_STORE_BACKEND=inmemory. Doi sang chroma neu muon retrieval dung collection nay."
                showIcon
                type="info"
              />
            ) : null}

            {!snapshot.isAvailable ? (
              <Card title="Lenh ingest de tao collection">
                <Typography.Paragraph>
                  Chay lenh nay trong root project, sau do bam Tai lai:
                </Typography.Paragraph>
                <pre className="debug-command">{snapshot.ingestCommand}</pre>
              </Card>
            ) : null}

            <Row gutter={[16, 16]}>
              <Col lg={12} xs={24}>
                <Card title="Chunks by topic">
                  {topicRows.length ? (
                    <Table
                      columns={countColumns}
                      dataSource={topicRows}
                      pagination={false}
                      rowKey="name"
                      size="middle"
                    />
                  ) : (
                    <Empty description="Chua co topic trong Chroma" />
                  )}
                </Card>
              </Col>
              <Col lg={12} xs={24}>
                <Card title="Chunks by level">
                  {levelRows.length ? (
                    <Table
                      columns={countColumns}
                      dataSource={levelRows}
                      pagination={false}
                      rowKey="name"
                      size="middle"
                    />
                  ) : (
                    <Empty description="Chua co level trong Chroma" />
                  )}
                </Card>
              </Col>
            </Row>

            <Card
              title={
                <Space>
                  <FileSearchOutlined />
                  <span>Sample chunks</span>
                </Space>
              }
            >
              {snapshot.sampleChunks.length ? (
                <Table
                  columns={chunkColumns}
                  dataSource={snapshot.sampleChunks}
                  pagination={false}
                  rowKey="chunkId"
                  scroll={{ x: 920 }}
                />
              ) : (
                <Empty description="Chua co sample chunk de hien thi" />
              )}
            </Card>
          </Space>
        ) : null}
      </main>
    </ConfigProvider>
  );
}

function toCountRows(counts: Record<string, number>): CountRow[] {
  return Object.entries(counts)
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
}

function formatCode(value: string) {
  return value.replace(/_/g, " ");
}
