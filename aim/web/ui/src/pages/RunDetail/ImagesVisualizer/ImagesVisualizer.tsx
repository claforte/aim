import React, { memo } from 'react';
import { useResizeObserver } from 'hooks';

import { Slider, Tooltip } from '@material-ui/core';

import { MediaTypeEnum } from 'components/MediaPanel/config';
import MediaPanel from 'components/MediaPanel';
import BusyLoaderWrapper from 'components/BusyLoaderWrapper/BusyLoaderWrapper';
import ErrorBoundary from 'components/ErrorBoundary/ErrorBoundary';

import {
  ImageRenderingEnum,
  MediaItemAlignmentEnum,
} from 'config/enums/imageEnums';

import blobsURIModel from 'services/models/media/blobsURIModel';
import imagesExploreService from 'services/api/imagesExplore/imagesExploreService';

import {
  decodeBufferPairs,
  decodePathsVals,
  iterFoldTree,
} from 'utils/encoder/streamEncoding';
import arrayBufferToBase64 from 'utils/arrayBufferToBase64';

import { IImagesVisualizerProps } from '../types';

import './ImagesVisualizer.scss';

const MEDIA_ITEM_SIZE_KEY = 'runDetailImagesMediaItemSize';
const DEFAULT_MEDIA_ITEM_SIZE = 25;

function getInitialMediaItemSize(): number {
  const stored = Number(localStorage.getItem(MEDIA_ITEM_SIZE_KEY));
  return stored >= 10 && stored <= 95 ? stored : DEFAULT_MEDIA_ITEM_SIZE;
}

function ImagesVisualizer(
  props: IImagesVisualizerProps | any,
): React.FunctionComponentElement<React.ReactNode> {
  const { data, isLoading } = props;
  const imagesWrapperRef = React.useRef<any>(null);
  const [focusedState, setFocusedState] = React.useState({
    active: false,
    key: null,
  });
  const [offsetHeight, setOffsetHeight] = React.useState(
    imagesWrapperRef?.current?.offsetHeight,
  );
  const [offsetWidth, setOffsetWidth] = React.useState(
    imagesWrapperRef?.current?.offsetWidth,
  );

  useResizeObserver(
    () => setOffsetWidth(imagesWrapperRef?.current?.offsetWidth),
    imagesWrapperRef,
  );

  React.useEffect(() => {
    blobsURIModel.init();
  }, []);

  React.useEffect(() => {
    setOffsetHeight(imagesWrapperRef?.current?.offsetHeight);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imagesWrapperRef?.current?.offsetHeight]);

  function getImagesBlobsData(uris: string[]) {
    const request = imagesExploreService.getImagesByURIs(uris);
    return {
      abort: request.abort,
      call: () => {
        return request
          .call()
          .then(async (stream) => {
            let bufferPairs = decodeBufferPairs(stream);
            let decodedPairs = decodePathsVals(bufferPairs);
            let objects = iterFoldTree(decodedPairs, 1);
            for await (let [keys, val] of objects) {
              const URI = keys[0];
              blobsURIModel.emit(URI as string, {
                [URI]: arrayBufferToBase64(val as ArrayBuffer) as string,
              });
            }
          })
          .catch((ex) => {
            if (ex.name !== 'AbortError') {
              // eslint-disable-next-line no-console
              console.log('Unhandled error: ');
            }
            // rethrow so the caller (MediaPanel) can re-queue the affected URIs
            throw ex;
          });
      },
    };
  }

  const onActivePointChange = React.useCallback(
    (activePoint: any, focusedStateActive: boolean = false) => {
      setFocusedState({ key: activePoint.key, active: focusedStateActive });
    },
    [],
  );

  const [mediaItemSize, setMediaItemSize] = React.useState<number>(
    getInitialMediaItemSize,
  );

  const additionalProperties = React.useMemo(() => {
    return {
      alignmentType: MediaItemAlignmentEnum.Height,
      mediaItemSize,
      imageRendering: ImageRenderingEnum.Pixelated,
    };
  }, [mediaItemSize]);

  const controls = React.useMemo(
    () => (
      <div className='ImagesVisualizer__sizeControl'>
        <Tooltip title='Image size' placement='left'>
          <span className='ImagesVisualizer__sizeControl__sliderBox'>
            <Slider
              orientation='vertical'
              value={mediaItemSize}
              min={10}
              max={95}
              step={5}
              onChange={(e, value) => setMediaItemSize(value as number)}
              onChangeCommitted={(e, value) =>
                localStorage.setItem(MEDIA_ITEM_SIZE_KEY, String(value))
              }
            />
          </span>
        </Tooltip>
      </div>
    ),
    [mediaItemSize],
  );

  const sortFieldsDict = React.useMemo(() => {
    return {
      step: {
        group: 'record',
        label: 'record.step',
        value: 'step',
        readonly: false,
        order: 'desc',
      },
    };
  }, []);

  return (
    <ErrorBoundary>
      <BusyLoaderWrapper
        className='VisualizationLoader'
        isLoading={!!props.isLoading}
      >
        <div className='ImagesVisualizer' ref={imagesWrapperRef}>
          <MediaPanel
            mediaType={MediaTypeEnum.IMAGE}
            getBlobsData={getImagesBlobsData}
            data={data?.imageSetData}
            orderedMap={data?.orderedMap}
            isLoading={!data || isLoading}
            panelResizing={false}
            tableHeight={'0'}
            wrapperOffsetHeight={offsetHeight || 0}
            wrapperOffsetWidth={offsetWidth || 0}
            sortFieldsDict={sortFieldsDict}
            focusedState={focusedState}
            controls={controls}
            additionalProperties={additionalProperties}
            onActivePointChange={onActivePointChange}
            illustrationConfig={{ title: 'No Tracked Images' }}
          />
        </div>
      </BusyLoaderWrapper>
    </ErrorBoundary>
  );
}

ImagesVisualizer.displayName = 'ImagesVisualizer';

export default memo<IImagesVisualizerProps>(ImagesVisualizer);
