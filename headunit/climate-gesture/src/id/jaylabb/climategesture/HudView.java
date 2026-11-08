package id.jaylabb.climategesture;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.view.View;

/**
 * The see-through card shown while the gesture runs: a vertical temperature pill (cold blue at the
 * bottom, warm orange at the top) and a 10-segment fan bar. The axis in use is bright, the other dim.
 */
final class HudView extends View {
    static final int W = 760, H = 480;
    static final int MODE_BOTH = 0, MODE_FAN = 1, MODE_TEMP = 2;

    private static final int COLD = 0xFF3FA9F5, MID = 0xFFE8EEF3, WARM = 0xFFFF7A3D, FAN = 0xFF4FC3F7;

    private final Paint card = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint pill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint track = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint knob = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint big = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint small = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint seg = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint icon = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF r = new RectF();

    int mode = MODE_BOTH;
    int fan = -1;    // 1..10, -1 unknown
    int temp = -1;   // 0..30 steps, -1 unknown

    HudView(Context c) {
        super(c);
        card.setColor(0xE6121820);
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeWidth(2);
        stroke.setColor(0x33FFFFFF);
        track.setColor(0x26FFFFFF);
        knob.setColor(Color.WHITE);
        knob.setShadowLayer(10, 0, 3, 0x80000000);
        big.setColor(Color.WHITE);
        big.setTypeface(Typeface.create("sans-serif-light", Typeface.NORMAL));
        big.setTextSize(132);
        small.setColor(0xB3FFFFFF);
        small.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        small.setTextSize(30);
        small.setLetterSpacing(0.08f);
        icon.setColor(Color.WHITE);
        setLayerType(LAYER_TYPE_SOFTWARE, null); // shadow layer on the knob
    }

    @Override protected void onMeasure(int w, int h) { setMeasuredDimension(W, H); }

    @Override protected void onDraw(Canvas c) {
        r.set(0, 0, W, H);
        c.drawRoundRect(r, 56, 56, card);
        r.inset(1, 1);
        c.drawRoundRect(r, 55, 55, stroke);

        int tempAlpha = mode == MODE_FAN ? 90 : 255;
        int fanAlpha = mode == MODE_TEMP ? 90 : 255;

        // --- temperature pill (left) ---
        float px = 56, py = 48, pw = 112, ph = H - 96;
        pill.setShader(new LinearGradient(0, py + ph, 0, py, new int[]{COLD, MID, WARM}, null, Shader.TileMode.CLAMP));
        pill.setAlpha(tempAlpha);
        r.set(px, py, px + pw, py + ph);
        c.drawRoundRect(r, pw / 2, pw / 2, pill);
        if (temp >= 0) {
            float f = temp / 30f;
            float ky = py + ph - pw / 2 - f * (ph - pw);
            knob.setAlpha(tempAlpha);
            c.drawCircle(px + pw / 2, ky, pw / 2 - 12, knob);
        }

        // --- temperature number (right, top) ---
        float tx = 232;
        big.setAlpha(tempAlpha);
        String t = temp >= 0 ? Car.tempLabel(temp) : "--";
        c.drawText(t, tx, 210, big);
        float tw = big.measureText(t);
        small.setAlpha(tempAlpha);
        small.setTextSize(44);
        c.drawText("°C", tx + tw + 10, 150, small);
        small.setTextSize(28);
        small.setAlpha(Math.min(tempAlpha, 160));
        c.drawText(mode == MODE_BOTH ? "↕  SUHU" : "SUHU", tx + 4, 92, small);

        // --- fan bar (right, bottom) ---
        float fy = 300, iconSize = 84;
        drawFan(c, tx + iconSize / 2, fy + iconSize / 2, iconSize / 2 - 4, fanAlpha);
        float bx = tx + iconSize + 28, bw = W - 56 - bx, gap = 8, sw = (bw - gap * 9) / 10f;
        for (int i = 0; i < 10; i++) {
            float x0 = bx + i * (sw + gap);
            float hgt = 26 + i * 4.4f;
            r.set(x0, fy + iconSize - hgt - 4, x0 + sw, fy + iconSize - 4);
            boolean lit = fan > i;
            seg.setColor(lit ? FAN : 0x26FFFFFF);
            seg.setAlpha(lit ? fanAlpha : 60);
            c.drawRoundRect(r, 6, 6, seg);
        }
        small.setTextSize(28);
        small.setAlpha(Math.min(fanAlpha, 160));
        String fl = (mode == MODE_BOTH ? "↔  KIPAS" : "KIPAS") + (fan > 0 ? "   " + fan : "");
        c.drawText(fl, tx + 4, fy - 24, small);
    }

    /** Our own four-blade fan glyph (no head-unit artwork). */
    private void drawFan(Canvas c, float cx, float cy, float rad, int alpha) {
        icon.setAlpha(alpha);
        c.save();
        c.translate(cx, cy);
        for (int k = 0; k < 4; k++) {
            c.save();
            c.rotate(k * 90f + 18f);
            r.set(-rad * 0.30f, -rad, rad * 0.30f, -rad * 0.14f);
            c.drawOval(r, icon);
            c.restore();
        }
        c.drawCircle(0, 0, rad * 0.16f, icon);
        c.restore();
    }
}
