import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = path.join(__dirname, "..", "screenshots");

test.describe("Chat reply e2e", () => {
  test("should receive a real text reply after sending 'hi'", async ({
    page,
  }) => {
    // Collect browser console messages for debugging
    const consoleErrors: string[] = [];
    const networkErrors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    page.on("requestfailed", (request) => {
      networkErrors.push(`${request.method()} ${request.url()} - ${request.failure()?.errorText}`);
    });

    // 1. Navigate to the app
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // 2. Open the chat panel by clicking the floating chat button
    const toggle = page.locator('[class*="chatButton"]');
    await toggle.waitFor({ state: "visible", timeout: 10000 });
    await toggle.click();

    // 3. Wait for the chat input to be visible
    const chatInput = page.locator("input#chat");
    await expect(chatInput).toBeVisible({ timeout: 5000 });

    // 4. Click the input and type "hi"
    await chatInput.click();
    await chatInput.fill("hi");

    // 5. Click the send message button
    const sendButton = page.locator('button[title="Send Message"]');
    await sendButton.click();

    // 6. Wait for the dot-pulse loading animation to appear
    const dotPulse = page.locator('[data-title="dotpulse"]');
    await dotPulse
      .waitFor({ state: "visible", timeout: 10000 })
      .catch(() => {});

    // 7. Wait for the loading dots to disappear (response arrived)
    //    Give the backend up to 60s to respond
    const replyArrived = await dotPulse
      .waitFor({ state: "hidden", timeout: 60000 })
      .then(() => true)
      .catch(() => false);

    // 8. Always capture a screenshot of the chat window
    const chatSection = page.locator('[class*="chatSection"]');
    await chatSection.screenshot({
      path: path.join(SCREENSHOT_DIR, "chat-reply.png"),
    });

    // Also capture a full-page screenshot for context
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "chat-reply-fullpage.png"),
      fullPage: true,
    });

    // 9. Assert the reply arrived (dots gone)
    if (!replyArrived) {
      const debugInfo = [
        `Console errors (${consoleErrors.length}): ${consoleErrors.join("; ") || "none"}`,
        `Network failures (${networkErrors.length}): ${networkErrors.join("; ") || "none"}`,
      ].join("\n");
      console.log("Debug info:\n" + debugInfo);

      throw new Error(
        "FAIL: The assistant reply never arrived — the 3-dot loading animation " +
          "was still visible after 60s. The backend may not be responding.\n" +
          `Screenshots saved to ${SCREENSHOT_DIR}/\n${debugInfo}`
      );
    }

    // 10. Verify we got actual text content, not empty
    const assistantMessages = page.locator('[class*="messageAssistant"]');
    const lastAssistant = assistantMessages.last();
    await expect(lastAssistant).toBeVisible({ timeout: 5000 });

    const replyText = await lastAssistant.textContent();
    expect(replyText).toBeTruthy();
    expect(replyText!.trim().length).toBeGreaterThan(0);

    // Confirm no loading dots remain
    await expect(dotPulse).not.toBeVisible();

    // Final screenshot with the successful reply
    await chatSection.screenshot({
      path: path.join(SCREENSHOT_DIR, "chat-reply-success.png"),
    });

    console.log(
      `SUCCESS: Assistant replied with: "${replyText!.trim().substring(0, 100)}..."`
    );
  });
});
