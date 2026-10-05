import {
  EmptyView,
  ErrorView,
  LoadingView,
} from "../../../shared/components";


export type TrendListFeedbackProps =
  | {
      state: "loading";
    }
  | {
      state: "empty";
      filtered: boolean;
    }
  | {
      state: "error";
      onRetry: () => void;
      retrying: boolean;
    };

export function TrendListFeedback(
  props: TrendListFeedbackProps,
) {
  switch (props.state) {
    case "loading":
      return (
        <LoadingView
          message="최신 트렌드를 불러오고 있습니다."
        />
      );

    case "empty":
      return (
        <EmptyView
          title={
            props.filtered
              ? "이 분야에 표시할 트렌드가 없습니다."
              : "표시할 트렌드가 없습니다."
          }
        />
      );

    case "error":
      return (
        <ErrorView
          message="잠시 후 다시 시도해 주세요."
          onRetry={props.onRetry}
          retrying={props.retrying}
          title="최신 트렌드를 불러오지 못했습니다."
        />
      );
  }
}
