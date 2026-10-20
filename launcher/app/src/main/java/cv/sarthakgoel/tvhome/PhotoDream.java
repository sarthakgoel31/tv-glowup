package cv.sarthakgoel.tvhome;

import android.service.dreams.DreamService;

/** Screensaver: the family photos chosen in Family Photos, one every 30 seconds. Any key wakes the TV. */
public class PhotoDream extends DreamService {
    private PhotoSlideshow show;

    @Override
    public void onAttachedToWindow() {
        super.onAttachedToWindow();
        setInteractive(false);
        setFullscreen(true);
        show = new PhotoSlideshow(this);
        setContentView(show);
    }

    @Override
    public void onDreamingStarted() {
        super.onDreamingStarted();
        show.start(PhotoStore.selected(this));
    }

    @Override
    public void onDreamingStopped() {
        show.stop();
        super.onDreamingStopped();
    }

    @Override
    public void onDetachedFromWindow() {
        show.release();
        super.onDetachedFromWindow();
    }
}
