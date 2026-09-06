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
  const hasMessage = !!(e && e.gmail && e.gmail.messageId);

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
        'Open PrivacyGate → Protect → Gmail and copy the pairing code shown there.'
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
        .setOnClickAction(CardService.newAction().setFunctionName('unpairPrivacyGateDevice'))
    );
  } else {
    section.addWidget(
      CardService.newTextParagraph().setText(
        '<b>Ready to send this selected email.</b><br>' +
        'PrivacyGate will receive this message and its supported attachments once. ' +
        'It does not receive access to the rest of your mailbox.'
      )
    );
    section.addWidget(
      CardService.newTextButton()
        .setText('Send to PrivacyGate')
        .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
        .setOnClickAction(CardService.newAction().setFunctionName('sendCurrentMessageToPrivacyGate'))
    );
    section.addWidget(
      CardService.newTextButton()
        .setText('Pair another device')
        .setOnClickAction(CardService.newAction().setFunctionName('unpairPrivacyGateDevice'))
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
    GmailApp.setCurrentMessageAccessToken(e.gmail.accessToken);
    const message = GmailApp.getMessageById(e.gmail.messageId);
    if (!message) {
      throw new Error('Gmail did not return the selected message.');
    }

    const payload = {
      message_id: String(e.gmail.messageId || ''),
      thread_id: String(e.gmail.threadId || ''),
      subject: String(message.getSubject() || '(No subject)'),
      sender: String(message.getFrom() || ''),
      recipients: String(message.getTo() || ''),
      sent_at: formatDate_(message.getDate()),
      body: String(message.getPlainBody() || ''),
      attachments: collectAttachments_(message)
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
        CardService.newNotification().setText('Sent to PrivacyGate. Return to Protect.')
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

function collectAttachments_(message) {
  const attachments = message.getAttachments({
    includeInlineImages: false,
    includeAttachments: true
  }) || [];

  return attachments.map(function(blob) {
    return {
      filename: String(blob.getName() || 'attachment.bin'),
      mime_type: String(blob.getContentType() || 'application/octet-stream'),
      data_b64: stripPadding_(Utilities.base64EncodeWebSafe(blob.getBytes()))
    };
  });
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

function jsonResponse_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
