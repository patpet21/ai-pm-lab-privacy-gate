const PG_PAIRING_PROPERTY = 'privacygate_device_channel';
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
  const channel = PropertiesService.getUserProperties().getProperty(PG_PAIRING_PROPERTY) || '';
  const hasMessage = !!(e && e.gmail && e.gmail.messageId && e.gmail.accessToken);

  const builder = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle('PrivacyGate')
        .setSubtitle('Review the open email before sending it to Protect')
    );

  const section = CardService.newCardSection();

  if (!channel) {
    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>Connect PrivacyGate once.</b><br>' +
        'Open PrivacyGate → Protect → Gmail and paste the pairing code below.'
      )
    );
    section.addWidget(
      CardService.newTextInput()
        .setFieldName('pairing_code')
        .setTitle('PrivacyGate pairing code')
        .setHint('Paste the one-time code from PrivacyGate')
    );
    section.addWidget(
      CardService.newTextButton()
        .setText('Pair with PrivacyGate')
        .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
        .setOnClickAction(CardService.newAction().setFunctionName('pairPrivacyGateDevice'))
    );
    builder.addSection(section);
    return builder.build();
  }

  if (!hasMessage) {
    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>PrivacyGate is connected.</b><br>' +
        'Open an email in Gmail. The PrivacyGate panel will show that message before you send it to Protect.'
      )
    );
    section.addWidget(
      CardService.newTextButton()
        .setText('Pair another device')
        .setOnClickAction(CardService.newAction().setFunctionName('unpairPrivacyGateDevice'))
    );
    builder.addSection(section);
    return builder.build();
  }

  try {
    const message = readCurrentMessage_(e);
    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>' + escapeHtml_(message.subject || '(No subject)') + '</b><br>' +
        '<font color="#607789">' + escapeHtml_(message.sender || 'Unknown sender') + '</font>' +
        (message.sent_at ? '<br><font color="#607789">' + escapeHtml_(message.sent_at) + '</font>' : '')
      )
    );

    const preview = String(message.body || '').trim();
    section.addWidget(
      CardService.newTextParagraph().setText(
        preview
          ? escapeHtml_(preview.substring(0, 1400)) + (preview.length > 1400 ? '…' : '')
          : '<font color="#607789">No plain-text body available.</font>'
      )
    );

    const attachmentCount = Number(message.attachment_count || 0);
    if (attachmentCount > 0) {
      section.addWidget(
        CardService.newTextParagraph().setText(
          '<b>Attachments:</b> ' + attachmentCount +
          ' supported file' + (attachmentCount === 1 ? '' : 's')
        )
      );
    }

    section.addWidget(
      CardService.newTextButton()
        .setText('Open in PrivacyGate')
        .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
        .setOnClickAction(
          CardService.newAction()
            .setFunctionName('sendCurrentMessageToPrivacyGate')
            .setLoadIndicator(CardService.LoadIndicator.SPINNER)
        )
    );
    section.addWidget(
      CardService.newTextParagraph().setText(
        '<font color="#607789">Only this open message is sent after you press “Open in PrivacyGate”. ' +
        'PrivacyGate does not receive mailbox-wide access.</font>'
      )
    );
    section.addWidget(
      CardService.newTextButton()
        .setText('Pair another device')
        .setOnClickAction(CardService.newAction().setFunctionName('unpairPrivacyGateDevice'))
    );
  } catch (err) {
    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>Unable to preview this message.</b><br>' +
        escapeHtml_(String(err && err.message ? err.message : err))
      )
    );
  }

  builder.addSection(section);
  return builder.build();
}

function pairPrivacyGateDevice(e) {
  const raw = readFormString_(e, 'pairing_code').trim();
  if (!/^[A-Za-z0-9_-]{16,64}$/.test(raw)) {
    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification().setText('Paste the pairing code shown in PrivacyGate.')
      )
      .build();
  }

  PropertiesService.getUserProperties().setProperty(PG_PAIRING_PROPERTY, raw);
  CacheService.getScriptCache().put('pg:paired:' + hashChannel_(raw), '1', PG_PAIRING_MARKER_TTL_SECONDS);

  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText('PrivacyGate paired.'))
    .setNavigation(CardService.newNavigation().updateCard(buildPrivacyGateCard(e)))
    .build();
}

function unpairPrivacyGateDevice(e) {
  PropertiesService.getUserProperties().deleteProperty(PG_PAIRING_PROPERTY);
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText('PrivacyGate device pairing cleared.'))
    .setNavigation(CardService.newNavigation().updateCard(buildPrivacyGateCard(e)))
    .build();
}

function sendCurrentMessageToPrivacyGate(e) {
  const channel = PropertiesService.getUserProperties().getProperty(PG_PAIRING_PROPERTY) || '';
  if (!channel) {
    return CardService.newActionResponseBuilder()
      .setNotification(CardService.newNotification().setText('Pair PrivacyGate first.'))
      .setNavigation(CardService.newNavigation().updateCard(buildPrivacyGateCard(e)))
      .build();
  }
  if (!(e && e.gmail && e.gmail.messageId && e.gmail.accessToken)) {
    return CardService.newActionResponseBuilder()
      .setNotification(CardService.newNotification().setText('Open a Gmail message first.'))
      .build();
  }

  try {
    const message = readCurrentMessage_(e, true);
    const payload = {
      message_id: String(e.gmail.messageId || ''),
      thread_id: String(e.gmail.threadId || ''),
      subject: String(message.subject || '(No subject)'),
      sender: String(message.sender || ''),
      recipients: String(message.recipients || ''),
      sent_at: String(message.sent_at || ''),
      body: String(message.body || ''),
      attachments: message.attachments || []
    };

    const json = JSON.stringify(payload);
    const payloadB64 = stripPadding_(Utilities.base64EncodeWebSafe(json, Utilities.Charset.UTF_8));
    if (payloadB64.length > PG_MAX_ENCODED_PAYLOAD) {
      throw new Error(
        'This email is too large for the temporary Gmail transfer. ' +
        'Use PrivacyGate Upload for large attachments.'
      );
    }

    const signature = stripPadding_(
      Utilities.base64EncodeWebSafe(
        Utilities.computeHmacSha256Signature(payloadB64, channel, Utilities.Charset.UTF_8)
      )
    );

    writePayload_(channel, payloadB64, signature);

    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification().setText('Opened in PrivacyGate. Return to Protect.')
      )
      .build();
  } catch (err) {
    return CardService.newActionResponseBuilder()
      .setNotification(
        CardService.newNotification().setText(String(err && err.message ? err.message : err))
      )
      .build();
  }
}

function readCurrentMessage_(e, includeAttachmentBytes) {
  GmailApp.setCurrentMessageAccessToken(e.gmail.accessToken);
  const message = GmailApp.getMessageById(e.gmail.messageId);
  if (!message) {
    throw new Error('Gmail did not return the open message.');
  }

  const attachments = message.getAttachments({
    includeInlineImages: false,
    includeAttachments: true
  }) || [];

  return {
    subject: String(message.getSubject() || '(No subject)'),
    sender: String(message.getFrom() || ''),
    recipients: String(message.getTo() || ''),
    sent_at: formatDate_(message.getDate()),
    body: String(message.getPlainBody() || ''),
    attachment_count: attachments.length,
    attachments: includeAttachmentBytes
      ? attachments.map(function(blob) {
          return {
            filename: String(blob.getName() || 'attachment.bin'),
            mime_type: String(blob.getContentType() || 'application/octet-stream'),
            data_b64: stripPadding_(Utilities.base64EncodeWebSafe(blob.getBytes()))
          };
        })
      : []
  };
}

function doPost(e) {
  try {
    const request = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const action = String(request.action || '');
    const channel = String(request.channel || '').trim();

    if (!/^[A-Za-z0-9_-]{16,64}$/.test(channel)) {
      return jsonResponse_({ok: false, error: 'Invalid device channel.'});
    }

    if (action === 'status') {
      const paired = !!CacheService.getScriptCache().get('pg:paired:' + hashChannel_(channel));
      return jsonResponse_({ok: true, paired: paired});
    }

    if (action === 'poll') {
      return pollPayload_(channel);
    }

    return jsonResponse_({ok: false, error: 'Unsupported action.'});
  } catch (err) {
    return jsonResponse_({
      ok: false,
      error: String(err && err.message ? err.message : err)
    });
  }
}

function pollPayload_(channel) {
  const cache = CacheService.getScriptCache();
  const channelHash = hashChannel_(channel);
  const manifestKey = 'pg:message:' + channelHash;
  const manifestRaw = cache.get(manifestKey);
  if (!manifestRaw) {
    return jsonResponse_({ok: true, ready: false});
  }

  const manifest = JSON.parse(manifestRaw);
  const chunkCount = Number(manifest.chunks || 0);
  const nonce = String(manifest.nonce || '');
  if (!nonce || chunkCount < 1 || chunkCount > 200) {
    cache.remove(manifestKey);
    return jsonResponse_({ok: false, error: 'Invalid temporary Gmail payload.'});
  }

  const keys = [];
  for (let i = 0; i < chunkCount; i++) {
    keys.push('pg:chunk:' + channelHash + ':' + nonce + ':' + i);
  }
  const values = cache.getAll(keys);
  let payloadB64 = '';
  for (let i = 0; i < keys.length; i++) {
    if (!(keys[i] in values)) {
      return jsonResponse_({ok: true, ready: false});
    }
    payloadB64 += values[keys[i]];
  }

  cache.remove(manifestKey);
  cache.removeAll(keys);

  return jsonResponse_({
    ok: true,
    ready: true,
    payload_b64: payloadB64,
    signature: String(manifest.signature || '')
  });
}

function writePayload_(channel, payloadB64, signature) {
  const cache = CacheService.getScriptCache();
  const channelHash = hashChannel_(channel);
  const nonce = Utilities.getUuid().replace(/-/g, '');
  const chunks = [];

  for (let offset = 0; offset < payloadB64.length; offset += PG_CACHE_CHUNK_SIZE) {
    chunks.push(payloadB64.substring(offset, offset + PG_CACHE_CHUNK_SIZE));
  }

  const values = {};
  const keys = [];
  chunks.forEach(function(chunk, index) {
    const key = 'pg:chunk:' + channelHash + ':' + nonce + ':' + index;
    keys.push(key);
    values[key] = chunk;
  });
  cache.putAll(values, PG_CACHE_TTL_SECONDS);

  const manifestKey = 'pg:message:' + channelHash;
  cache.put(
    manifestKey,
    JSON.stringify({
      nonce: nonce,
      chunks: chunks.length,
      signature: signature,
      created_at: new Date().toISOString()
    }),
    PG_CACHE_TTL_SECONDS
  );
}

function readFormString_(e, fieldName) {
  try {
    const formInputs = e.commonEventObject && e.commonEventObject.formInputs;
    const entry = formInputs && formInputs[fieldName];
    const values = entry && entry.stringInputs && entry.stringInputs.value;
    if (values && values.length) {
      return String(values[0] || '');
    }
  } catch (err) {
    // Keep the compatibility fallback below.
  }
  try {
    return String((e.formInput && e.formInput[fieldName]) || '');
  } catch (err2) {
    return '';
  }
}

function hashChannel_(channel) {
  const digest = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    channel,
    Utilities.Charset.UTF_8
  );
  return digest.map(function(value) {
    const unsigned = value < 0 ? value + 256 : value;
    return ('0' + unsigned.toString(16)).slice(-2);
  }).join('').substring(0, 32);
}

function stripPadding_(value) {
  return String(value || '').replace(/=+$/, '');
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
    .replace(/'/g, '&#39;')
    .replace(/\n/g, '<br>');
}

function jsonResponse_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
