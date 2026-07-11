import React from 'react';

import PopoverContent from 'components/ChartPanel/PopoverContent/PopoverContent';
import { Button, Icon, Text } from 'components/kit';
import ErrorBoundary from 'components/ErrorBoundary/ErrorBoundary';

import blobsURIModel from 'services/models/media/blobsURIModel';

import { ChartTypeEnum } from 'utils/d3';

import { IImageFullViewPopoverProps } from './types.d';

import './styles.scss';

const MIN_ZOOM = 0.05;
const MAX_ZOOM = 64;
const ZOOM_STEP = 1.25;

function ImageFullViewPopover({
  imageRendering,
  imageData,
  tooltipContent,
  handleClose,
  selectOptions,
  onRunsTagsChange,
}: IImageFullViewPopoverProps): React.FunctionComponentElement<React.ReactNode> {
  const blobData = blobsURIModel.getState()[imageData?.blob_uri];
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  // null zoom = fit-to-viewport (upscaling allowed — small images fill the screen)
  const [zoom, setZoom] = React.useState<number | null>(null);
  const [fitScale, setFitScale] = React.useState<number>(1);
  const [sidebarOpen, setSidebarOpen] = React.useState<boolean>(true);

  const computeFit = React.useCallback((): number => {
    const el = containerRef.current;
    if (!el || !imageData?.width || !imageData?.height) {
      return 1;
    }
    const pad = 16;
    return Math.max(
      MIN_ZOOM,
      Math.min(
        (el.clientWidth - pad) / imageData.width,
        (el.clientHeight - pad) / imageData.height,
      ),
    );
  }, [imageData]);

  React.useEffect(() => {
    function update(): void {
      setFitScale(computeFit());
    }
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [computeFit, sidebarOpen]);

  const scale = zoom ?? fitScale;

  const applyZoom = React.useCallback(
    (next: number, cx?: number, cy?: number): void => {
      const el = containerRef.current;
      const clamped = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next));
      if (el && cx !== undefined && cy !== undefined) {
        const rect = el.getBoundingClientRect();
        const cur = zoom ?? fitScale;
        const px = (el.scrollLeft + cx - rect.left) / cur;
        const py = (el.scrollTop + cy - rect.top) / cur;
        setZoom(clamped);
        window.requestAnimationFrame(() => {
          el.scrollLeft = px * clamped - (cx - rect.left);
          el.scrollTop = py * clamped - (cy - rect.top);
        });
      } else {
        setZoom(clamped);
      }
    },
    [zoom, fitScale],
  );

  // native listener: React's delegated wheel events are passive, so
  // preventDefault (needed to stop page scroll while zooming) is ignored there
  React.useEffect(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    function onWheel(e: WheelEvent): void {
      e.preventDefault();
      const cur = zoom ?? fitScale;
      applyZoom(
        e.deltaY < 0 ? cur * ZOOM_STEP : cur / ZOOM_STEP,
        e.clientX,
        e.clientY,
      );
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [applyZoom, zoom, fitScale]);

  return (
    <ErrorBoundary>
      <div className='ImageFullViewPopover'>
        <div className='ImageFullViewPopover__imageArea'>
          <div className='ImageFullViewPopover__toolbar'>
            <Button
              onClick={() => setZoom(null)}
              size='small'
              color={zoom === null ? 'primary' : 'inherit'}
            >
              Fit
            </Button>
            <Button
              onClick={() => setZoom(1)}
              size='small'
              color={zoom === 1 ? 'primary' : 'inherit'}
            >
              1:1
            </Button>
            <Button
              withOnlyIcon
              size='small'
              color='inherit'
              onClick={() => applyZoom(scale / ZOOM_STEP)}
            >
              <Icon name='zoom-out' />
            </Button>
            <Button
              withOnlyIcon
              size='small'
              color='inherit'
              onClick={() => applyZoom(scale * ZOOM_STEP)}
            >
              <Icon name='zoom-in' />
            </Button>
            <Text size={12} className='ImageFullViewPopover__toolbar__zoomText'>
              {Math.round(scale * 100)}%
            </Text>
            <Text size={12} className='ImageFullViewPopover__toolbar__dimsText'>
              {imageData.width}×{imageData.height}
            </Text>
            <div className='ImageFullViewPopover__toolbar__spacer' />
            <Button
              withOnlyIcon
              size='small'
              color='inherit'
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              <Icon name={sidebarOpen ? 'arrow-right' : 'arrow-left'} />
            </Button>
            <Button
              withOnlyIcon
              size='small'
              color='inherit'
              onClick={handleClose}
            >
              <Icon name='close' />
            </Button>
          </div>
          <div
            ref={containerRef}
            className={`ImageFullViewPopover__imageContainer ImageFullViewPopover__imageContainer--${imageRendering}`}
          >
            <div className='ImageFullViewPopover__imageContainer__imageBox'>
              <img
                src={`data:image/${imageData.format};base64, ${blobData}`}
                style={{
                  width: imageData.width * scale,
                  height: imageData.height * scale,
                  maxWidth: 'none',
                  maxHeight: 'none',
                }}
                alt={imageData.caption}
              />
            </div>
          </div>
        </div>
        {sidebarOpen && (
          <div className='ImageFullViewPopover__detailContainer'>
            <div className='ImageFullViewPopover__detailContainer__content'>
              <ErrorBoundary>
                <PopoverContent
                  chartType={ChartTypeEnum.ImageSet}
                  tooltipContent={tooltipContent}
                  focusedState={{ active: true, key: null }}
                  selectOptions={selectOptions}
                  onRunsTagsChange={onRunsTagsChange}
                />
              </ErrorBoundary>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}

ImageFullViewPopover.displayName = 'ImageFullViewPopover';

export default React.memo<IImageFullViewPopoverProps>(ImageFullViewPopover);
