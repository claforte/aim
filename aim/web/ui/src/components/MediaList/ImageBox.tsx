import React from 'react';
import classNames from 'classnames';

import { Skeleton } from '@material-ui/lab';
import { Dialog } from '@material-ui/core';

import { Button, Icon, Text } from 'components/kit';
import ImageFullViewPopover from 'components/ImageFullViewPopover';
import ErrorBoundary from 'components/ErrorBoundary/ErrorBoundary';

import { BATCH_COLLECT_DELAY } from 'config/mediaConfigs/mediaConfigs';
import { MediaItemAlignmentEnum } from 'config/enums/imageEnums';
import { ANALYTICS_EVENT_KEYS } from 'config/analytics/analyticsKeysMap';

import blobsURIModel from 'services/models/media/blobsURIModel';
import * as analytics from 'services/analytics';

import { IImageBoxProps } from './MediaList.d';

const ImageBox = ({
  index,
  style,
  data,
  addUriToList,
  mediaItemHeight,
  focusedState,
  tooltip,
  additionalProperties,
  selectOptions,
  onRunsTagsChange,
}: IImageBoxProps): React.FunctionComponentElement<React.ReactNode> => {
  const { format, blob_uri } = data;
  const [isImageFullViewPopupOpened, setIsImageFullViewPopupOpened] =
    React.useState<boolean>(false);
  let [blobData, setBlobData] = React.useState<string>(
    blobsURIModel.getState()[blob_uri] ?? null,
  );

  React.useEffect(() => {
    let timeoutID: number;
    let subscription: any;
    let pollCount = 0;

    // Bounded poll instead of a one-shot fallback: this effect's cleanup runs
    // on every parent re-render (addUriToList is recreated each render), so
    // the subscription can be torn down while the batched blob response is
    // still streaming. A model emit landing in that gap — after the single
    // timeout had already fired and addUriToList refused the still-"processed"
    // URI — left a permanent skeleton until the tile was remounted
    // (found 2026-07-10: blob batches returned 200 yet tiles stayed blank;
    // re-selecting the image rendered instantly from the cache).
    function pollBlob() {
      timeoutID = window.setTimeout(() => {
        if (blobsURIModel.getState()[blob_uri]) {
          setBlobData(blobsURIModel.getState()[blob_uri]);
          if (subscription) {
            subscription.unsubscribe();
          }
        } else {
          addUriToList(blob_uri);
          if (pollCount++ < 150) {
            pollBlob();
          }
        }
      }, BATCH_COLLECT_DELAY);
    }

    if (blobData === null) {
      if (blobsURIModel.getState()[blob_uri]) {
        setBlobData(blobsURIModel.getState()[blob_uri]);
      } else {
        subscription = blobsURIModel.subscribe(blob_uri, (data) => {
          setBlobData(data[blob_uri]);
          subscription.unsubscribe();
        });
        pollBlob();
      }
    }

    return () => {
      if (timeoutID) {
        clearTimeout(timeoutID);
      }
      if (subscription) {
        subscription.unsubscribe();
      }
    };
  }, [addUriToList, blobData, blob_uri]);

  function onImageFullSizeModeButtonClick(e: React.ChangeEvent<any>): void {
    e.stopPropagation();
    setIsImageFullViewPopupOpened(true);
    analytics.trackEvent(
      ANALYTICS_EVENT_KEYS.images.imagesPanel.openFullSizeMode,
    );
  }

  const skeletonSize = {
    width: style.width - 6, // 6px -> 0.375rem gap
    height:
      additionalProperties.alignmentType !== MediaItemAlignmentEnum.Height
        ? style.width / (data.width / data.height) - 6 // 6px -> 0.375rem gap
        : mediaItemHeight - 40,
    containerWidth: style.width - 4,
    containerHeight:
      additionalProperties.alignmentType !== MediaItemAlignmentEnum.Height
        ? style.width / (data.width / data.height) - 4
        : mediaItemHeight - 40,
  };

  return (
    <ErrorBoundary key={index}>
      <div className='ImageBox' style={style}>
        <div
          className={classNames('ImageBox__image', {
            [`ImageBox__image--${additionalProperties.imageRendering}`]:
              !!additionalProperties.imageRendering,
            focus: focusedState.key === data.key && focusedState?.active,
            active: focusedState.key === data.key && !focusedState?.active,
          })}
          data-key={`${data.key}`}
          data-seqkey={`${data.seqKey}`}
          data-mediasetitem='mediaSetItem'
        >
          <div className='ImageBox__imageWrapper'>
            <div
              className={`ImageBox__imageWrapper-item ${
                additionalProperties.alignmentType ===
                MediaItemAlignmentEnum.Height
                  ? 'ImageBox__imageWrapper-item-heightAlign'
                  : ''
              }`}
            >
              {blobData ? (
                <img
                  src={`data:image/${format};base64, ${blobData}`}
                  alt={data.caption}
                />
              ) : (
                <div
                  style={{
                    height: skeletonSize.containerHeight,
                    width: skeletonSize.containerWidth,
                  }}
                  className='skeletonContainer'
                >
                  <Skeleton
                    variant='rect'
                    height={skeletonSize.height}
                    width={skeletonSize.width}
                  />
                </div>
              )}
              <Text style={{ maxWidth: style.width }} size={10} weight={400}>
                {data.caption}
              </Text>
            </div>
            <Button
              withOnlyIcon
              size='small'
              className={classNames('ImageBox__imageWrapper__zoomIconWrapper', {
                isHidden: focusedState.key !== data.key,
              })}
              onClick={onImageFullSizeModeButtonClick}
              color='inherit'
            >
              <Icon name='zoom-in' fontSize={14} />
            </Button>
          </div>
        </div>
        <ErrorBoundary>
          <Dialog
            onClose={() => setIsImageFullViewPopupOpened(false)}
            aria-labelledby='customized-dialog-title'
            className='MediaPanel__Container__imageFullViewPopup'
            open={isImageFullViewPopupOpened}
          >
            <ImageFullViewPopover
              imageRendering={additionalProperties?.imageRendering}
              tooltipContent={
                tooltip?.content || {
                  context: data.context,
                  step: data.step,
                  index: data.index,
                  caption: data.caption,
                  images_name: data.name,
                }
              }
              selectOptions={selectOptions}
              imageData={data}
              handleClose={() => setIsImageFullViewPopupOpened(false)}
              onRunsTagsChange={onRunsTagsChange}
            />
          </Dialog>
        </ErrorBoundary>
      </div>
    </ErrorBoundary>
  );
};

export default ImageBox;
