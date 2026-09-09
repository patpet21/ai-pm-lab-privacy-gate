const PG_PAIRING_PROPERTY = 'privacygate_device_channel';
const PG_REVIEW_MODE_PROPERTY = 'privacygate_google_review_mode';
const PG_GOOGLE_REVIEW_CODE_PROPERTY = 'PG_GOOGLE_REVIEW_CODE';

const PG_CACHE_TTL_SECONDS = 120;
const PG_PAIRING_MARKER_TTL_SECONDS = 600;
const PG_CACHE_CHUNK_SIZE = 80000;
const PG_MAX_ENCODED_PAYLOAD = 7500000;

function onHomepage(e) {
  return buildPrivacyGateCard(e || {});
}

function onGmailMessageOpen(e) {
  return buildPrivacyGateCard(e || {});
}

function buildPrivacyGateCard(e) {
  const userProperties = PropertiesService.getUserProperties();

  const channel =
    userProperties.getProperty(PG_PAIRING_PROPERTY) || '';

  const reviewMode =
    userProperties.getProperty(PG_REVIEW_MODE_PROPERTY) === '1';

  const hasMessage =
    !!(e && e.gmail && e.gmail.messageId);

  const builder = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle('PrivacyGate')
        .setSubtitle('Send only the email you choose')
    );

  const section = CardService.newCardSection();

  if (!channel) {
    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>Pair this Gmail add-on with PrivacyGate once.</b><br>' +
        'Open PrivacyGate → Apps → Gmail → Add Gmail account. ' +
        'Copy the code for this account. Use a different card for each Gmail account.'
      )
    );

    section.addWidget(
      CardService.newTextInput()
        .setFieldName('pairing_code')
        .setTitle('PrivacyGate pairing code')
        .setHint('Paste this account’s pairing code from Apps')
    );

    section.addWidget(
      CardService.newTextButton()
        .setText('Connect')
        .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
        .setOnClickAction(
          CardService.newAction()
            .setFunctionName('pairPrivacyGateDevice')
        )
    );

  } else if (reviewMode && !hasMessage) {

    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>Google Workspace Marketplace review mode is active.</b><br>' +
        'Open any email in Gmail. This panel will then allow you to test access to only that selected message. ' +
        'No PrivacyGate desktop installation is required for this review flow.'
      )
    );

    section.addWidget(
      CardService.newTextButton()
        .setText('Exit reviewer mode')
        .setOnClickAction(
          CardService.newAction()
            .setFunctionName('unpairPrivacyGateDevice')
        )
    );

  } else if (reviewMode && hasMessage) {

    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>Reviewer test ready.</b><br>' +
        'Click Send to PrivacyGate to verify that PrivacyGate accesses only this explicitly selected Gmail message. ' +
        'In reviewer mode, the test does not require the PrivacyGate desktop application and no email content is stored or transmitted outside this Apps Script review flow.'
      )
    );

    section.addWidget(
      CardService.newTextButton()
        .setText('Send to PrivacyGate')
        .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
        .setOnClickAction(
          CardService.newAction()
            .setFunctionName('sendCurrentMessageToPrivacyGate')
        )
    );

    section.addWidget(
      CardService.newTextButton()
        .setText('Exit reviewer mode')
        .setOnClickAction(
          CardService.newAction()
            .setFunctionName('unpairPrivacyGateDevice')
        )
    );

  } else if (!hasMessage) {

    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>PrivacyGate is paired.</b><br>' +
        'Open an email in Gmail. This panel will then let you send that selected message to PrivacyGate.'
      )
    );

    section.addWidget(
      CardService.newTextButton()
        .setText('Pair another device')
        .setOnClickAction(
          CardService.newAction()
            .setFunctionName('unpairPrivacyGateDevice')
        )
    );

  } else {

    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>Ready to send this selected email.</b><br>' +
        'Click Send to PrivacyGate. If PrivacyGate desktop is running and this account is paired, ' +
        'the selected email will appear automatically for local review and protection. ' +
        'Only this selected email is transferred; PrivacyGate does not access the rest of your mailbox.'
      )
    );

    section.addWidget(
      CardService.newTextButton()
        .setText('Send to PrivacyGate')
        .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
        .setOnClickAction(
          CardService.newAction()
            .setFunctionName('sendCurrentMessageToPrivacyGate')
        )
    );

    section.addWidget(
      CardService.newTextButton()
        .setText('Pair another device')
        .setOnClickAction(
          CardService.newAction()
            .setFunctionName('unpairPrivacyGateDevice')
        )
    );
  }

  builder.addSection(section);

  return builder.build();
}

function pairPrivacyGateDevice(e) {
  const raw =
    readFormString_(e, 'pairing_code').trim();

  if (!/^[A-Za-z0-9_-]{16,64}$/.test(raw)) {
    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification()
          .setText('Paste the pairing code shown in PrivacyGate.')
      )
      .build();
  }

  const reviewCode =
    PropertiesService
      .getScriptProperties()
      .getProperty(PG_GOOGLE_REVIEW_CODE_PROPERTY) || '';

  const userProperties =
    PropertiesService.getUserProperties();

  if (reviewCode && raw === reviewCode) {
    userProperties.setProperty(
      PG_PAIRING_PROPERTY,
      raw
    );

    userProperties.setProperty(
      PG_REVIEW_MODE_PROPERTY,
      '1'
    );

    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification()
          .setText('PrivacyGate reviewer mode connected.')
      )
      .setNavigation(
        CardService.newNavigation()
          .updateCard(buildPrivacyGateCard(e))
      )
      .build();
  }

  userProperties.setProperty(
    PG_PAIRING_PROPERTY,
    raw
  );

  userProperties.deleteProperty(
    PG_REVIEW_MODE_PROPERTY
  );

  CacheService
    .getScriptCache()
    .put(
      'pg:paired:' + hashChannel_(raw),
      '1',
      PG_PAIRING_MARKER_TTL_SECONDS
    );

  return CardService.newActionResponseBuilder()
    .setNotification(
      CardService.newNotification()
        .setText('PrivacyGate paired.')
    )
    .setNavigation(
      CardService.newNavigation()
        .updateCard(buildPrivacyGateCard(e))
    )
    .build();
}

function unpairPrivacyGateDevice(e) {
  const userProperties =
    PropertiesService.getUserProperties();

  userProperties.deleteProperty(
    PG_PAIRING_PROPERTY
  );

  userProperties.deleteProperty(
    PG_REVIEW_MODE_PROPERTY
  );

  return CardService.newActionResponseBuilder()
    .setNotification(
      CardService.newNotification()
        .setText('PrivacyGate device pairing cleared.')
    )
    .setNavigation(
      CardService.newNavigation()
        .updateCard(buildPrivacyGateCard(e))
    )
    .build();
}

function sendCurrentMessageToPrivacyGate(e) {
  const userProperties =
    PropertiesService.getUserProperties();

  const channel =
    userProperties.getProperty(PG_PAIRING_PROPERTY) || '';

  const reviewMode =
    userProperties.getProperty(PG_REVIEW_MODE_PROPERTY) === '1';

  if (!channel) {
    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification()
          .setText('Pair PrivacyGate first.')
      )
      .setNavigation(
        CardService.newNavigation()
          .updateCard(buildPrivacyGateCard(e))
      )
      .build();
  }

  if (!(e && e.gmail && e.gmail.messageId && e.gmail.accessToken)) {
    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification()
          .setText('Open a Gmail message first.')
      )
      .build();
  }

  try {
    GmailApp.setCurrentMessageAccessToken(
      e.gmail.accessToken
    );

    const message =
      GmailApp.getMessageById(
        e.gmail.messageId
      );

    if (!message) {
      throw new Error(
        'Gmail did not return the selected message.'
      );
    }

    if (reviewMode) {
      return CardService.newActionResponseBuilder()
        .setNotification(
          CardService.newNotification()
            .setText('Reviewer test completed successfully.')
        )
        .setNavigation(
          CardService.newNavigation()
            .updateCard(
              buildGoogleReviewResultCard_(message, e)
            )
        )
        .build();
    }

    const payload = {
      message_id: String(
        e.gmail.messageId || ''
      ),

      thread_id: String(
        e.gmail.threadId || ''
      ),

      subject: String(
        message.getSubject() || '(No subject)'
      ),

      sender: String(
        message.getFrom() || ''
      ),

      recipients: String(
        message.getTo() || ''
      ),

      sent_at: formatDate_(
        message.getDate()
      ),

      body: String(
        message.getPlainBody() || ''
      ),

      attachments: collectAttachments_(
        message
      )
    };

    const json =
      JSON.stringify(payload);

    const payloadB64 =
      stripPadding_(
        Utilities.base64EncodeWebSafe(
          json,
          Utilities.Charset.UTF_8
        )
      );

    if (
      payloadB64.length >
      PG_MAX_ENCODED_PAYLOAD
    ) {
      throw new Error(
        'This email is too large for the temporary Gmail transfer. ' +
        'Use PrivacyGate Upload for large attachments.'
      );
    }

    const signature =
      stripPadding_(
        Utilities.base64EncodeWebSafe(
          Utilities.computeHmacSha256Signature(
            payloadB64,
            channel,
            Utilities.Charset.UTF_8
          )
        )
      );

    writePayload_(
      channel,
      payloadB64,
      signature
    );

    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification()
          .setText('Sent to PrivacyGate. Return to Protect.')
      )
      .build();

  } catch (err) {
    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification()
          .setText(
            String(
              err && err.message
                ? err.message
                : err
            )
          )
      )
      .build();
  }
}

function buildGoogleReviewResultCard_(message, e) {
  const subject =
    escapeHtml_(
      String(
        message.getSubject() || '(No subject)'
      )
    );

  const sender =
    escapeHtml_(
      String(
        message.getFrom() || ''
      )
    );

  const recipients =
    escapeHtml_(
      String(
        message.getTo() || ''
      )
    );

  const sentAt =
    escapeHtml_(
      formatDate_(
        message.getDate()
      )
    );

  const body =
    String(
      message.getPlainBody() || ''
    );

  const attachments =
    message.getAttachments({
      includeInlineImages: false,
      includeAttachments: true
    }) || [];

  const builder =
    CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle('PrivacyGate')
          .setSubtitle('Google Workspace Marketplace review')
      );

  const section =
    CardService.newCardSection();

  section.addWidget(
    CardService.newTextParagraph()
      .setText(
        '<b>Reviewer test completed successfully.</b><br><br>' +
        'PrivacyGate accessed only the Gmail message that you explicitly selected and opened.'
      )
  );

  section.addWidget(
    CardService.newDecoratedText()
      .setTopLabel('Selected message subject')
      .setText(subject)
  );

  section.addWidget(
    CardService.newDecoratedText()
      .setTopLabel('Sender')
      .setText(sender || '(Not available)')
  );

  section.addWidget(
    CardService.newDecoratedText()
      .setTopLabel('Recipients')
      .setText(recipients || '(Not available)')
  );

  section.addWidget(
    CardService.newDecoratedText()
      .setTopLabel('Message date')
      .setText(sentAt || '(Not available)')
  );

  section.addWidget(
    CardService.newDecoratedText()
      .setTopLabel('Message body detected')
      .setText(
        body.length +
        ' characters'
      )
  );

  section.addWidget(
    CardService.newDecoratedText()
      .setTopLabel('Attachments detected')
      .setText(
        String(attachments.length)
      )
  );

  section.addWidget(
    CardService.newTextParagraph()
      .setText(
        '<b>Privacy note</b><br>' +
        'Reviewer mode does not store this email, write it to the PrivacyGate transfer cache, ' +
        'or transmit it to an external PrivacyGate service. ' +
        'The production workflow sends only the explicitly selected message to the user’s paired PrivacyGate desktop application for local review and protection.'
      )
  );

  section.addWidget(
    CardService.newTextButton()
      .setText('Back')
      .setOnClickAction(
        CardService.newAction()
          .setFunctionName('returnToPrivacyGateCard')
      )
  );

  section.addWidget(
    CardService.newTextButton()
      .setText('Exit reviewer mode')
      .setOnClickAction(
        CardService.newAction()
          .setFunctionName('unpairPrivacyGateDevice')
      )
  );

  builder.addSection(section);

  return builder.build();
}

function returnToPrivacyGateCard(e) {
  return CardService.newActionResponseBuilder()
    .setNavigation(
      CardService.newNavigation()
        .updateCard(buildPrivacyGateCard(e))
    )
    .build();
}

function doPost(e) {
  try {
    const request =
      JSON.parse(
        (
          e &&
          e.postData &&
          e.postData.contents
        ) || '{}'
      );

    const action =
      String(
        request.action || ''
      );

    const channel =
      String(
        request.channel || ''
      ).trim();

    if (
      !/^[A-Za-z0-9_-]{16,64}$/.test(
        channel
      )
    ) {
      return jsonResponse_({
        ok: false,
        error: 'Invalid device channel.'
      });
    }

    if (action === 'status') {
      const paired =
        !!CacheService
          .getScriptCache()
          .get(
            'pg:paired:' +
            hashChannel_(channel)
          );

      return jsonResponse_({
        ok: true,
        paired: paired
      });
    }

    if (action === 'poll') {
      return pollPayload_(channel);
    }

    return jsonResponse_({
      ok: false,
      error: 'Unsupported action.'
    });

  } catch (err) {
    return jsonResponse_({
      ok: false,
      error: String(
        err && err.message
          ? err.message
          : err
      )
    });
  }
}

function pollPayload_(channel) {
  const cache =
    CacheService.getScriptCache();

  const channelHash =
    hashChannel_(channel);

  const manifestKey =
    'pg:message:' +
    channelHash;

  const manifestRaw =
    cache.get(manifestKey);

  if (!manifestRaw) {
    return jsonResponse_({
      ok: true,
      ready: false
    });
  }

  const manifest =
    JSON.parse(
      manifestRaw
    );

  const chunkCount =
    Number(
      manifest.chunks || 0
    );

  const nonce =
    String(
      manifest.nonce || ''
    );

  if (
    !nonce ||
    chunkCount < 1 ||
    chunkCount > 200
  ) {
    cache.remove(
      manifestKey
    );

    return jsonResponse_({
      ok: false,
      error:
        'Invalid temporary Gmail payload.'
    });
  }

  const keys = [];

  for (
    let i = 0;
    i < chunkCount;
    i++
  ) {
    keys.push(
      'pg:chunk:' +
      channelHash +
      ':' +
      nonce +
      ':' +
      i
    );
  }

  const values =
    cache.getAll(keys);

  let payloadB64 = '';

  for (
    let i = 0;
    i < keys.length;
    i++
  ) {
    if (
      !(keys[i] in values)
    ) {
      return jsonResponse_({
        ok: true,
        ready: false
      });
    }

    payloadB64 +=
      values[keys[i]];
  }

  cache.remove(
    manifestKey
  );

  cache.removeAll(
    keys
  );

  return jsonResponse_({
    ok: true,
    ready: true,
    payload_b64:
      payloadB64,
    signature:
      String(
        manifest.signature || ''
      )
  });
}

function writePayload_(
  channel,
  payloadB64,
  signature
) {
  const cache =
    CacheService.getScriptCache();

  const channelHash =
    hashChannel_(channel);

  const nonce =
    Utilities
      .getUuid()
      .replace(
        /-/g,
        ''
      );

  const chunks = [];

  for (
    let offset = 0;
    offset < payloadB64.length;
    offset += PG_CACHE_CHUNK_SIZE
  ) {
    chunks.push(
      payloadB64.substring(
        offset,
        offset + PG_CACHE_CHUNK_SIZE
      )
    );
  }

  const values = {};
  const keys = [];

  chunks.forEach(
    function(chunk, index) {
      const key =
        'pg:chunk:' +
        channelHash +
        ':' +
        nonce +
        ':' +
        index;

      keys.push(key);
      values[key] = chunk;
    }
  );

  cache.putAll(
    values,
    PG_CACHE_TTL_SECONDS
  );

  const manifestKey =
    'pg:message:' +
    channelHash;

  cache.put(
    manifestKey,
    JSON.stringify({
      nonce: nonce,
      chunks: chunks.length,
      signature: signature,
      created_at:
        new Date().toISOString()
    }),
    PG_CACHE_TTL_SECONDS
  );
}

function collectAttachments_(message) {
  const attachments =
    message.getAttachments({
      includeInlineImages: false,
      includeAttachments: true
    }) || [];

  return attachments.map(
    function(blob) {
      return {
        filename: String(
          blob.getName() ||
          'attachment.bin'
        ),

        mime_type: String(
          blob.getContentType() ||
          'application/octet-stream'
        ),

        data_b64:
          stripPadding_(
            Utilities.base64EncodeWebSafe(
              blob.getBytes()
            )
          )
      };
    }
  );
}

function readFormString_(
  e,
  fieldName
) {
  try {
    const formInputs =
      e.commonEventObject &&
      e.commonEventObject.formInputs;

    const entry =
      formInputs &&
      formInputs[fieldName];

    const values =
      entry &&
      entry.stringInputs &&
      entry.stringInputs.value;

    if (
      values &&
      values.length
    ) {
      return String(
        values[0] || ''
      );
    }

  } catch (err) {
  }

  try {
    return String(
      (
        e.formInput &&
        e.formInput[fieldName]
      ) || ''
    );

  } catch (err2) {
    return '';
  }
}

function hashChannel_(channel) {
  const digest =
    Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      channel,
      Utilities.Charset.UTF_8
    );

  return digest
    .map(
      function(value) {
        const unsigned =
          value < 0
            ? value + 256
            : value;

        return (
          '0' +
          unsigned.toString(16)
        ).slice(-2);
      }
    )
    .join('')
    .substring(
      0,
      32
    );
}

function stripPadding_(value) {
  return String(
    value || ''
  ).replace(
    /=+$/,
    ''
  );
}

function formatDate_(value) {
  if (!value) {
    return '';
  }

  try {
    return Utilities.formatDate(
      value,
      Session.getScriptTimeZone() || 'UTC',
      "yyyy-MM-dd'T'HH:mm:ssXXX"
    );

  } catch (err) {
    return String(value);
  }
}

function escapeHtml_(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function jsonResponse_(payload) {
  return ContentService
    .createTextOutput(
      JSON.stringify(payload)
    )
    .setMimeType(
      ContentService.MimeType.JSON
    );
}
