import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth0 } from "@auth0/auth0-react";
import apiService from '../apiService';
import styles from '../styles';
import LoadingSpinner from './loadingSpinner';
import LinkCopyButton from './linkCopyButton';

const Bot = () => {
  const { isAuthenticated, user, isLoading: authLoading } = useAuth0();
  const { id } = useParams();
  const [botDetails, setBotDetails] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [botError, setBotError] = useState(false);
  const [loading, setLoading] = useState(false);
  const isMobile = window.innerWidth <= 768;
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const getBotDetails = async () => {
      try {
        const botDetails = await apiService.getBots({ id }, true);
        if (!botDetails?.length) {
          setBotError(true);
          return;
        }

        setBotDetails(botDetails[0]);
        setMessages(prev => prev.length === 0 ? [
          ...(isMobile ? [
            { sender: 'system', text: `Starting chat with - ${botDetails[0].name}` },
            { sender: 'system', text: `Description - ${botDetails[0].description}` }
          ] : []),
          ...(botDetails[0]?.greetingText ? [{ sender: 'bot', text: botDetails[0].greetingText }] : [])
        ] : prev);
      } catch (error) {
        console.error(`Error fetching bot details for bot (${id}):`, error);
        setBotError(true);
      }
    };

    if (isAuthenticated) {
      getBotDetails();
    }
  }, [id, isMobile, isAuthenticated]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSendMessage = async () => {
    if (input.trim()) {
      const userMessage = { sender: 'user', text: input };
      const tempAllMessages = [...messages, userMessage];
      setMessages(tempAllMessages);
      setInput('');
      setLoading(true);

      try {
        const botResponse = await apiService.chat(botDetails, tempAllMessages, user.sub);
        setMessages(prevMessages => [...prevMessages, { sender: 'bot', text: botResponse?.message || "Error. Try again later." }]);
      } catch (error) {
        console.error("Error sending chat message:", error);
        setMessages(prevMessages => [...prevMessages, { sender: 'bot', text: "Error. Try again later." }]);
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    }
  };

  return (
    <>
      <div style={isMobile ? styles.chatContainerMobile : styles.chatContainer}>
        {authLoading ? <LoadingSpinner /> : (
          isAuthenticated ? (
            botError ? (
              <h3>Error retrieving bot ({id}). Try again later.</h3>
            ) : botDetails ? (
              <>
                {!isMobile && (
                  <>
                    <div style={{ display: 'flex' }}>
                      <h2 style={{ ...styles.botTitle, ...isMobile ? styles.mobileSubHeader : {}, marginRight: '1rem' }}>
                        Chat with {botDetails.name}
                      </h2>
                      <LinkCopyButton botId={botDetails.id} />
                    </div>
                    <p style={{ ...styles.botDescription, ...isMobile ? { ...styles.mobileSubText, paddingTop: 0 } : {} }}>
                      {botDetails.description}
                    </p>
                    <hr />
                  </>
                )}

                <div style={isMobile ? styles.messagesContainerMobile : styles.messagesContainer}>
                  {messages.map((message, index) => (
                    <div key={index} style={{
                      ...(message.sender === 'user' ? styles.userMessage :
                        message.sender === 'bot' ? styles.botMessage : styles.systemMessage),
                      ...(isMobile ? styles.mobileSubText : {})
                    }}>
                      <strong>{message.sender === 'user' ? 'You' : message.sender === 'bot' ? 'Bot' : 'System'}:</strong> {message.text}
                    </div>
                  ))}
                  {loading && <div style={styles.botMessage}><strong>Bot:</strong> Typing...</div>}
                  <div ref={messagesEndRef} />
                </div>
              </>
            ) : (
              <LoadingSpinner />
            )
          ) : (
            <h3>Please login to access this chat.</h3>
          )
        )}
      </div>

      <form style={{ ...styles.inputContainer, ...(!isMobile ? { maxWidth: '600px', margin: 'auto' } : {}) }} onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}>
        <input
          type="text"
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Type a message..."
          disabled={loading}
          style={{ ...styles.chatInput, ...(isMobile ? styles.mobileSubText : {}) }}
        />
        <button type="submit" disabled={loading || !isAuthenticated} style={{ ...styles.sendButton, ...(isMobile ? styles.mobileButton : {}) }}>
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </>
  );
};

export default Bot;
