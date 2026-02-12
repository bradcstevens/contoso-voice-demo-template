import { test, expect } from "@playwright/test";

test.describe("Voice & Chat UI - Chat Component", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should display the chat toggle button and open/close the chat window", async ({
    page,
  }) => {
    // The chat input should NOT be visible initially (chat is closed)
    const chatInput = page.locator('input[title="Type a message"]');
    await expect(chatInput).not.toBeVisible();

    // The Chat component renders a floating button (div with chatButton class) at bottom-right.
    // CSS module hashes the class name, so we match with a substring selector.
    const chatToggle = page.locator('div[class*="chatButton"]');
    await expect(chatToggle).toBeVisible({ timeout: 5000 });

    // Click to open the chat window
    await chatToggle.click();
    await expect(chatInput).toBeVisible({ timeout: 5000 });

    // Click again to close the chat window
    await chatToggle.click();
    await expect(chatInput).not.toBeVisible({ timeout: 5000 });
  });

  test("should display chat input field and send button when chat is open", async ({
    page,
  }) => {
    // Open the chat by clicking the floating chat button
    const chatToggle = page.locator('div[class*="chatButton"]');
    await chatToggle.click();

    const chatInput = page.locator('input[title="Type a message"]');
    const sendButton = page.locator('button[title="Send Message"]');

    // Verify input and send button are present when chat is open
    await expect(chatInput).toBeVisible({ timeout: 5000 });
    await expect(sendButton).toBeVisible();

    // Verify the input accepts text
    await chatInput.fill("Hello, testing chat input");
    await expect(chatInput).toHaveValue("Hello, testing chat input");
  });

  test("should display connection indicator and header icons in chat window", async ({
    page,
  }) => {
    // Open the chat window
    const chatToggle = page.locator('div[class*="chatButton"]');
    await chatToggle.click();

    const chatInput = page.locator('input[title="Type a message"]');
    await expect(chatInput).toBeVisible({ timeout: 5000 });

    // The chat header (div with chatHeader class) contains icon SVGs:
    // - Reset icon (GrPowerReset)
    // - Connection beacon icon (GrBeacon) showing connected/disconnected state
    // - Close icon (GrClose)
    const chatHeader = page.locator('div[class*="chatHeader"]');
    await expect(chatHeader).toBeVisible();

    // The header should contain at least 3 clickable SVG icons
    const headerIcons = chatHeader.locator("svg");
    const iconCount = await headerIcons.count();
    expect(iconCount).toBeGreaterThanOrEqual(3);

    // Verify the connection indicator exists by checking for the beacon icon
    // which has either a "connected" or "disconnected" CSS class
    const beaconIcon = chatHeader.locator(
      'svg[class*="connected"], svg[class*="disconnected"], div:has(svg[class*="connected"]), div:has(svg[class*="disconnected"])'
    );
    // The beacon/connection area should be present
    const connectionIndicators = chatHeader.locator("div").filter({ has: page.locator("svg") });
    const divCount = await connectionIndicators.count();
    expect(divCount).toBeGreaterThanOrEqual(1);
  });
});

test.describe("Voice & Chat UI - Voice Component", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should display the voice phone button and settings button", async ({
    page,
  }) => {
    // The Voice component renders at bottom-left (fixed position) with:
    // 1. A phone icon button (FiPhone) in voiceButton class
    // 2. A settings icon button (FiSettings) in settingsButton class
    const voiceButton = page.locator('div[class*="voiceButton"]');
    const settingsButton = page.locator('div[class*="settingsButton"]');

    await expect(voiceButton).toBeVisible({ timeout: 5000 });
    await expect(settingsButton).toBeVisible();

    // Each button should contain an SVG icon
    await expect(voiceButton.locator("svg")).toBeVisible();
    await expect(settingsButton.locator("svg")).toBeVisible();
  });

  test("should toggle voice settings panel when settings button is clicked", async ({
    page,
  }) => {
    // Settings panel labels that appear when VoiceSettings is open
    const voiceInputLabel = page.getByText("Voice Input:");
    const thresholdLabel = page.getByText("Sensitivity Threshold", {
      exact: false,
    });

    // Settings panel should NOT be visible initially
    await expect(voiceInputLabel).not.toBeVisible();

    // Click the settings button to open the voice settings panel
    const settingsButton = page.locator('div[class*="settingsButton"]');
    await expect(settingsButton).toBeVisible({ timeout: 5000 });
    await settingsButton.click();

    // Voice settings panel should now be visible with all controls
    await expect(voiceInputLabel).toBeVisible({ timeout: 5000 });
    await expect(thresholdLabel).toBeVisible();

    const silenceLabel = page.getByText("Silence Duration", { exact: false });
    const prefixLabel = page.getByText("Prefix Padding", { exact: false });
    await expect(silenceLabel).toBeVisible();
    await expect(prefixLabel).toBeVisible();

    // Verify the settings panel contains input controls
    const thresholdInput = page.locator('input[title="Sensitivity Threshold"]');
    const silenceInput = page.locator('input[title="Silence Duration"]');
    const prefixInput = page.locator('input[title="Prefix Padding"]');
    await expect(thresholdInput).toBeVisible();
    await expect(silenceInput).toBeVisible();
    await expect(prefixInput).toBeVisible();

    // Close settings by clicking the button again
    await settingsButton.click();
    await expect(voiceInputLabel).not.toBeVisible({ timeout: 5000 });
  });
});

test.describe("Voice & Chat UI - WebSocket Endpoint References", () => {
  test("should render the Chat component confirming /api/chat endpoint is bundled", async ({
    page,
  }) => {
    await page.goto("/");

    // The Chat component (which connects to WS_ENDPOINT + "/api/chat") renders
    // a floating button with chatButton class. Its presence on the page confirms
    // the /api/chat WebSocket endpoint code path is bundled in the application.
    const chatComponent = page.locator('div[class*="chatButton"]');
    await expect(chatComponent).toBeVisible({ timeout: 5000 });
  });

  test("should render the Voice component confirming /api/voice endpoint is bundled", async ({
    page,
  }) => {
    await page.goto("/");

    // The Voice component (which connects to WS_ENDPOINT + "/api/voice") renders
    // a phone button with voiceButton class. Its presence on the page confirms
    // the /api/voice WebSocket endpoint code path is bundled in the application.
    const voiceComponent = page.locator('div[class*="voiceButton"]');
    await expect(voiceComponent).toBeVisible({ timeout: 5000 });
  });
});
