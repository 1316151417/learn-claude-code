"""
K-means 聚类分析 Demo - 用户查询分类

这是一个教学示例，展示如何使用 K-means 对用户查询进行聚类分析。
流程：
1. 定义一组用户查询
2. 使用智谱 AI embedding-3 模型将文本向量化
3. 使用 K-means 进行聚类
4. 可视化聚类结果

依赖安装：
uv pip install zhipuai scikit-learn matplotlib numpy
"""

import os
from dotenv import load_dotenv
import numpy as np
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
from zai import ZhipuAiClient

# ==================== 配置中文字体（防止乱码）====================
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'STHeiti', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# ==================== 第一步：初始化智谱 Embedding 客户端 ====================
print(f"🔄 初始化智谱 AI Embedding 客户端...")

# 加载环境变量
load_dotenv()
zhipu_embedding_api_key = os.getenv("ZHIPUAI_EMBEDDING_API_KEY")

client = ZhipuAiClient(
    api_key=zhipu_embedding_api_key
)
EMBEDDING_MODEL = "embedding-3"
print("✓ 客户端初始化完成\n")

# ==================== 第二步：定义用户查询 ====================
# 16个示例查询，4个明显不同的类别（语义差异大）
queries = [
    # 编程技术类
    "Python 如何实现二叉树遍历算法",
    "JavaScript 中闭包是什么原理",
    "MySQL 数据库索引优化技巧",
    "Docker 容器部署 Spring Boot 应用",

    # 美食烹饪类
    "红烧肉的做法和配料比例",
    "四川麻婆豆腐怎么制作才正宗",
    "家常番茄炒蛋的美味秘诀",
    "意大利面酱汁的调制方法",

    # 体育运动类
    "篮球三分投篮的正确姿势",
    "足球世界杯冠军历史排行榜",
    "网球反手击球技术要点",
    "游泳自由泳换气技巧教学",

    # 旅游出行类
    "日本东京自由行攻略推荐",
    "云南丽江古城旅游注意事项",
    "巴黎埃菲尔铁塔门票价格",
    "海南三亚海景酒店预订建议",
]

print(f"📝 总共有 {len(queries)} 个用户查询\n")

# ==================== 第三步：向量化 ====================
print("🔄 正在调用智谱 Embedding API 进行向量化...")
print(f"   模型: {EMBEDDING_MODEL}\n")

embeddings = []
for query in queries:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[query]
    )
    embeddings.append(response.data[0].embedding)

embeddings = np.array(embeddings)
print(f"✓ 向量化完成，向量维度: {embeddings.shape}\n")

# ==================== 第四步：K-means 聚类 ====================
print("🔍 执行 K-means 聚类...")

# 设置聚类数量
n_clusters = 4
kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
labels = kmeans.fit_predict(embeddings)

print(f"✓ 聚类完成，共 {n_clusters} 个类别\n")

# ==================== 第五步：打印聚类结果 ====================
print("=" * 60)
print("📊 聚类结果")
print("=" * 60)

for i in range(n_clusters):
    print(f"\n【类别 {i}】")
    cluster_queries = [queries[j] for j in range(len(queries)) if labels[j] == i]
    for query in cluster_queries:
        print(f"  • {query}")

print("\n" + "=" * 60)

# ==================== 第六步：可视化 ====================
print("\n🎨 生成可视化图表...")

# 使用 t-SNE 进行降维（从1024维降到2维，便于可视化）
tsne = TSNE(n_components=2, random_state=42, perplexity=5)
embeddings_2d = tsne.fit_transform(embeddings)

# 绘制散点图
plt.figure(figsize=(12, 8))
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']

for i in range(n_clusters):
    mask = labels == i
    plt.scatter(
        embeddings_2d[mask, 0],
        embeddings_2d[mask, 1],
        c=colors[i],
        label=f'类别 {i}',
        s=100,
        alpha=0.7,
        edgecolors='white',
        linewidth=2
    )

# 添加查询标签
for i, (x, y) in enumerate(embeddings_2d):
    label = queries[i][:12] + "..." if len(queries[i]) > 12 else queries[i]
    plt.annotate(
        label,
        (x, y),
        xytext=(5, 5),
        textcoords='offset points',
        fontsize=8,
        alpha=0.8
    )

plt.title('用户查询 K-means 聚类结果 (智谱 Embedding + t-SNE)', fontsize=14, pad=20)
plt.xlabel('t-SNE 维度 1', fontsize=12)
plt.ylabel('t-SNE 维度 2', fontsize=12)
plt.legend(fontsize=10)
plt.grid(True, alpha=0.3)
plt.tight_layout()

# 保存图片
output_path = 'kmeans/cluster_result.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"✓ 可视化已保存到: {output_path}")

# 显示图表
plt.show()
