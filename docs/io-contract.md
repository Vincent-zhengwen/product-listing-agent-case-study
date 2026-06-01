# 输入输出结构

本仓库用桌布案例说明 Agent 的核心输入输出。公开样例保留足够的工程语义, 方便理解系统边界, 但不发布完整生产代码和原始页面快照。

## 输入

最小输入是一条货源链接:

```json
{
  "source_url": "https://www.yiwugo.com/product/detail/982191293.html",
  "target_platform": "taobao",
  "category_hint": "桌布 / 家纺软装"
}
```

完整输入可以包含用户补充信息:

```json
{
  "source_url": "https://www.yiwugo.com/product/detail/982191293.html",
  "target_platform": "taobao",
  "category_hint": "桌布 / 家纺软装",
  "preferred_sku_family": "棉麻彩色桌布",
  "publishing_goal": "生成可用于商品发布的标题、属性、主图和详情图"
}
```

货源也可以由检索工具根据关键词找到, 例如用户输入“棉麻桌布”“桌布 北美 跨境”等关键词后, 系统返回候选货源链接, 再进入同一条上架内容生成链路。

## 中间结构

Agent 在生成前会整理一份商品事实和规划结构:

```json
{
  "product_subject": "棉麻彩色桌布",
  "category": "桌布 / 家纺软装",
  "source_facts": {
    "material": "棉麻",
    "shape": "长方形",
    "style": "地中海风",
    "sizes": ["60*60cm", "90*90cm", "140*140cm", "140*180cm", "140*220cm"]
  },
  "main_image_jobs": [
    "铺桌首图",
    "尺寸规格",
    "面料纹理",
    "边缘垂坠",
    "浅底确认"
  ],
  "detail_jobs": [
    "场景效果",
    "卖点总览",
    "面料细节",
    "尺寸选择",
    "款式展示",
    "规格确认",
    "服务说明"
  ]
}
```

## 输出

最终输出是一套商品上架资产:

```json
{
  "title": "棉麻花朵桌布地中海风长方形餐桌台布",
  "attributes": {
    "材质": "棉麻",
    "类别": "桌布",
    "风格": "地中海风",
    "形状": "长方形",
    "颜色分类": "奈良油画风 / 大丽花 / 白须花边",
    "规格尺寸": "60*60cm 至 140*360cm 多规格"
  },
  "assets": {
    "main_images": 5,
    "detail_images": 8,
    "detail_full": "detail_full.jpg"
  }
}
```

完整样例见 [examples/tablecloth](../examples/tablecloth/README.md)。
