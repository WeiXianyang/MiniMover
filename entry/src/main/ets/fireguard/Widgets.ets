/**
 * FireGuard 通用 UI 组件
 * 对应页面原型 styles.css 中的 .pill / .card / .row / .metric / .recommend / .bar / .btn / .page-head
 */
import { FG } from './Theme';

/** 状态类型，对应 pill 的三种颜色 */
export enum FgStatus {
  Green = 0,
  Orange = 1,
  Red = 2
}

/** 状态徽标（pill） */
@Component
export struct FgPill {
  @Prop text: string = '';
  @Prop status: FgStatus = FgStatus.Green;

  private bgColor(): string {
    switch (this.status) {
      case FgStatus.Orange: return FG.pillOrangeBg;
      case FgStatus.Red: return FG.pillRedBg;
      default: return FG.pillGreenBg;
    }
  }

  private fontColorValue(): string {
    switch (this.status) {
      case FgStatus.Orange: return FG.pillOrangeText;
      case FgStatus.Red: return FG.pillRedText;
      default: return FG.pillGreenText;
    }
  }

  build() {
    Text(this.text)
      .fontSize(FG.smallSize)
      .fontWeight(FontWeight.Bold)
      .fontColor(this.fontColorValue())
      .textAlign(TextAlign.Center)
      .constraintSize({ maxWidth: 116 })
      .padding({ left: 10, right: 10, top: 7, bottom: 7 })
      .borderRadius(FG.pillRadius)
      .backgroundColor(this.bgColor())
  }
}

/** 页头：左侧标题+副标题，右侧状态徽标 */
@Component
export struct FgPageHead {
  @Prop title: string = '';
  @Prop subtitle: string = '';
  @Prop pillText: string = '';
  @Prop pillStatus: FgStatus = FgStatus.Green;

  build() {
    Row() {
      Column() {
        Text(this.title)
          .fontSize(FG.titleSize)
          .fontWeight(FontWeight.Bold)
          .fontColor(FG.text)
        Text(this.subtitle)
          .fontSize(FG.bodySize)
          .fontColor(FG.muted)
          .margin({ top: 8 })
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1)

      FgPill({ text: this.pillText, status: this.pillStatus })
    }
    .width('100%')
    .alignItems(VerticalAlign.Top)
    .margin({ bottom: 22 })
  }
}

/** 键值行（card 内的 .row） */
@Component
export struct FgRow {
  @Prop label: string = '';
  @Prop value: string = '';
  @Prop showBorder: boolean = true;

  build() {
    Row() {
      Text(this.label)
        .fontSize(FG.bodySize)
        .fontColor(FG.muted)
      Text(this.value)
        .fontSize(FG.bodySize)
        .fontColor(FG.text)
        .textAlign(TextAlign.End)
        .constraintSize({ maxWidth: '62%' })
        .layoutWeight(1)
        .margin({ left: 14 })
    }
    .width('100%')
    .justifyContent(FlexAlign.SpaceBetween)
    .padding({ top: 11, bottom: 11 })
    .border({ width: { bottom: this.showBorder ? 1 : 0 }, color: 'rgba(147, 164, 186, 0.18)' })
  }
}

/** 统计小卡（metric） */
@Component
export struct FgMetric {
  @Prop value: string = '';
  @Prop label: string = '';

  build() {
    Column() {
      Text(this.value)
        .fontSize(FG.metricSize)
        .fontWeight(FontWeight.Bold)
        .fontColor(FG.text)
      Text(this.label)
        .fontSize(FG.labelSize)
        .fontColor(FG.muted)
        .margin({ top: 8 })
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
    .constraintSize({ minHeight: 82 })
    .padding(15)
    .borderRadius(FG.cardRadius)
    .border({ width: 1, color: FG.line })
    .backgroundColor(FG.cardBg)
  }
}

/** 进度条（bar） */
@Component
export struct FgBar {
  @Prop percent: number = 0;

  build() {
    Row() {
      Row()
        .width(`${this.percent}%`)
        .height('100%')
        .borderRadius(FG.pillRadius)
        .linearGradient({
          angle: 90,
          colors: [[FG.orange, 0], [FG.cyan, 1]]
        })
    }
    .width('100%')
    .height(8)
    .margin({ top: 12 })
    .borderRadius(FG.pillRadius)
    .backgroundColor(FG.barTrack)
    .clip(true)
  }
}

/** 普通卡片容器（card） */
@Component
export struct FgCard {
  @BuilderParam content: () => void;

  build() {
    Column() {
      this.content()
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
    .padding(15)
    .margin({ bottom: 14 })
    .borderRadius(FG.cardRadius)
    .border({ width: 1, color: FG.line })
    .backgroundColor(FG.cardBg)
  }
}

/** 推荐/高亮卡片（recommend），橙色渐变高亮 */
@Component
export struct FgRecommend {
  @Prop label: string = '';
  @Prop title: string = '';
  @Prop desc: string = '';

  build() {
    Column() {
      if (this.label.length > 0) {
        Text(this.label)
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .margin({ bottom: 8 })
      }
      Text(this.title)
        .fontSize(FG.recommendSize)
        .fontWeight(FontWeight.Bold)
        .fontColor(FG.text)
        .lineHeight(FG.recommendSize * 1.35)
      if (this.desc.length > 0) {
        Text(this.desc)
          .fontSize(FG.labelSize)
          .fontColor(FG.muted)
          .lineHeight(FG.labelSize * 1.55)
          .margin({ top: 9 })
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
    .padding(15)
    .margin({ bottom: 14 })
    .borderRadius(FG.cardRadius)
    .border({ width: 1, color: 'rgba(255, 151, 72, 0.42)' })
    .linearGradient({
      angle: 135,
      colors: [['rgba(255, 151, 72, 0.17)', 0], [FG.cardBg, 1]]
    })
  }
}

/** 主按钮样式变体 */
export enum FgBtnType {
  Default = 0,
  Primary = 1,
  Danger = 2
}

/** 通用按钮（btn） */
@Component
export struct FgButton {
  @Prop text: string = '';
  @Prop type: FgBtnType = FgBtnType.Default;
  onTap: () => void = () => {};

  private bgColor(): string {
    switch (this.type) {
      case FgBtnType.Primary: return FG.orange;
      case FgBtnType.Danger: return FG.red;
      default: return FG.btnDefault;
    }
  }

  private fgColor(): string {
    switch (this.type) {
      case FgBtnType.Primary: return '#10151d';
      case FgBtnType.Danger: return '#ffffff';
      default: return FG.text;
    }
  }

  build() {
    Button(this.text)
      .fontSize(FG.bodySize)
      .fontWeight(FontWeight.Bold)
      .fontColor(this.fgColor())
      .type(ButtonType.Normal)
      .width('100%')
      .height(46)
      .borderRadius(FG.btnRadius)
      .backgroundColor(this.bgColor())
      .onClick(() => this.onTap())
  }
}
