# 棉麻彩色桌布案例

这个案例展示 Agent 如何把义乌购货源页转换成可发布的商品上架资产。

## 输入

- 货源链接: https://www.yiwugo.com/product/detail/982191293.html
- 原始商品: 跨境棉麻加厚彩色桌布花朵异域东南亚台布
- 商品类目: 桌布 / 家纺软装

原始货源页中既有商品事实, 也有批发和供货信息。Agent 需要保留材质、款式、尺寸和图片素材, 同时避免把代理、代发、跨境采购等供货语境带入 C 端商品页。

## 输出

- 标题: 棉麻花朵桌布地中海风长方形餐桌台布
- 主图: 5 张 800x800 JPG
- 详情图: 8 屏 750 宽 JPG
- 详情长图: 1 张拼接长图

生成图片位于:

```text
demo/assets/main_1.jpg
demo/assets/main_2.jpg
demo/assets/main_3.jpg
demo/assets/main_4.jpg
demo/assets/main_5.jpg
demo/assets/detail_01.jpg ... demo/assets/detail_08.jpg
demo/assets/detail_full.jpg
```

## 转换重点

| 原始货源信息 | 上架资产处理 |
|---|---|
| 批发、代理、代发、跨境供货信息 | 不进入买家页主表达 |
| 棉麻、桌布、长方形、多规格 | 进入标题、属性和详情参数 |
| 桌布场景图与款式图 | 用于铺桌首图、款式展示和详情场景 |
| 尺寸和规格信息 | 用于主图规格确认和详情尺寸模块 |
| 供货商语境 | 转译为低权重服务说明或完全移除 |

## 文件

- [input.json](input.json): 案例输入摘要。
- [output.json](output.json): 生成结果摘要。
- [demo/index.html](../../demo/index.html): 可直接打开的展示页面。
