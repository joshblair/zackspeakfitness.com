// Google Analytics Integration for Zack Speak Fitness

// Google Analytics 4 Configuration
const GA_MEASUREMENT_ID = 'G-XXXXXXXXXX'; // Replace with actual GA4 Measurement ID

// Initialize Google Analytics
function initGoogleAnalytics() {
    // Load Google Analytics script
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`;
    document.head.appendChild(script);
    
    // Initialize gtag
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    
    // Configure GA4
    gtag('config', GA_MEASUREMENT_ID, {
        // Privacy-focused configuration
        anonymize_ip: true,
        allow_google_signals: false,
        allow_ad_personalization_signals: false,
        
        // Enhanced measurement events
        enhanced_measurements: {
            scrolls: true,
            outbound_clicks: true,
            site_search: false,
            video_engagement: true,
            file_downloads: true
        },
        
        // Custom parameters
        custom_map: {
            'custom_parameter_1': 'fitness_goal',
            'custom_parameter_2': 'service_interest'
        }
    });
    
    // Make gtag globally available
    window.gtag = gtag;
}

// Event Tracking Functions
const Analytics = {
    // Page view tracking
    trackPageView: function(pagePath, pageTitle) {
        if (typeof gtag !== 'undefined') {
            gtag('config', GA_MEASUREMENT_ID, {
                page_path: pagePath,
                page_title: pageTitle
            });
        }
    },
    
    // Contact form events
    trackFormSubmission: function(formType, success = true) {
        if (typeof gtag !== 'undefined') {
            gtag('event', success ? 'form_submit' : 'form_error', {
                event_category: 'engagement',
                event_label: formType,
                value: success ? 1 : 0
            });
        }
    },
    
    // Service interest tracking
    trackServiceInterest: function(serviceName, action = 'click') {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'service_interest', {
                event_category: 'services',
                event_label: serviceName,
                custom_parameter_2: serviceName,
                action: action
            });
        }
    },
    
    // Calendly integration tracking
    trackCalendlyEvent: function(eventType) {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'calendly_interaction', {
                event_category: 'scheduling',
                event_label: eventType,
                value: eventType === 'scheduled' ? 10 : 1
            });
        }
    },
    
    // Navigation tracking
    trackNavigation: function(destination, source = 'navigation') {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'page_navigation', {
                event_category: 'navigation',
                event_label: `${source}_to_${destination}`,
                destination: destination
            });
        }
    },
    
    // Scroll depth tracking
    trackScrollDepth: function(percentage) {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'scroll', {
                event_category: 'engagement',
                event_label: `${percentage}%`,
                value: percentage
            });
        }
    },
    
    // Video engagement (for future video content)
    trackVideoEngagement: function(videoTitle, action, progress = 0) {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'video_engagement', {
                event_category: 'video',
                event_label: videoTitle,
                action: action,
                progress: progress
            });
        }
    },
    
    // Download tracking
    trackDownload: function(fileName, fileType) {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'file_download', {
                event_category: 'downloads',
                event_label: fileName,
                file_type: fileType
            });
        }
    },
    
    // Outbound link tracking
    trackOutboundClick: function(url, linkText) {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'click', {
                event_category: 'outbound',
                event_label: url,
                transport_type: 'beacon',
                link_text: linkText
            });
        }
    },
    
    // Error tracking
    trackError: function(errorType, errorMessage, page) {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'exception', {
                description: `${errorType}: ${errorMessage}`,
                fatal: false,
                page: page
            });
        }
    },
    
    // Custom conversion events
    trackConversion: function(conversionType, value = 1) {
        if (typeof gtag !== 'undefined') {
            gtag('event', 'conversion', {
                event_category: 'conversions',
                event_label: conversionType,
                value: value,
                currency: 'USD'
            });
        }
    }
};

// Automatic Event Tracking Setup
function setupAutomaticTracking() {
    // Track form submissions
    document.addEventListener('submit', function(e) {
        const form = e.target;
        const formId = form.id || 'unknown_form';
        
        // Track form start
        Analytics.trackFormSubmission(formId, true);
    });
    
    // Track service button clicks
    document.addEventListener('click', function(e) {
        const target = e.target;
        
        // Service interest buttons
        if (target.classList.contains('btn') && target.textContent.includes('Book')) {
            const serviceName = target.closest('.service-card')?.querySelector('h3')?.textContent || 'unknown_service';
            Analytics.trackServiceInterest(serviceName, 'book_click');
        }
        
        // Navigation links
        if (target.classList.contains('nav-link')) {
            const destination = target.textContent.toLowerCase();
            Analytics.trackNavigation(destination, 'main_nav');
        }
        
        // CTA buttons
        if (target.classList.contains('btn-primary')) {
            const buttonText = target.textContent.toLowerCase();
            if (buttonText.includes('schedule') || buttonText.includes('consultation')) {
                Analytics.trackConversion('consultation_click');
            }
        }
        
        // Outbound links
        if (target.tagName === 'A' && target.href && !target.href.includes(window.location.hostname)) {
            Analytics.trackOutboundClick(target.href, target.textContent);
        }
    });
    
    // Scroll depth tracking
    let maxScroll = 0;
    const scrollMilestones = [25, 50, 75, 90, 100];
    
    window.addEventListener('scroll', throttle(() => {
        const scrollPercent = Math.round(
            (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100
        );
        
        if (scrollPercent > maxScroll) {
            maxScroll = scrollPercent;
            
            // Track milestone achievements
            scrollMilestones.forEach(milestone => {
                if (scrollPercent >= milestone && maxScroll < milestone) {
                    Analytics.trackScrollDepth(milestone);
                }
            });
        }
    }, 1000));
    
    // Track page visibility changes
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            Analytics.trackPageView(window.location.pathname, document.title);
        }
    });
    
    // Track errors
    window.addEventListener('error', function(e) {
        Analytics.trackError('JavaScript Error', e.message, window.location.pathname);
    });
}

// Calendly Event Listeners
function setupCalendlyTracking() {
    // Listen for Calendly events if Calendly is loaded
    if (window.Calendly) {
        // Track when Calendly widget is opened
        document.addEventListener('calendly.event_type_viewed', function(e) {
            Analytics.trackCalendlyEvent('widget_opened');
        });
        
        // Track when event is scheduled
        document.addEventListener('calendly.event_scheduled', function(e) {
            Analytics.trackCalendlyEvent('scheduled');
            Analytics.trackConversion('consultation_scheduled', 50);
        });
    }
}

// Privacy and Consent Management
const PrivacyManager = {
    // Check if user has consented to analytics
    hasConsent: function() {
        return localStorage.getItem('analytics_consent') === 'true';
    },
    
    // Set user consent
    setConsent: function(consent) {
        localStorage.setItem('analytics_consent', consent.toString());
        
        if (consent) {
            this.enableAnalytics();
        } else {
            this.disableAnalytics();
        }
    },
    
    // Enable analytics tracking
    enableAnalytics: function() {
        if (typeof gtag !== 'undefined') {
            gtag('consent', 'update', {
                analytics_storage: 'granted'
            });
        }
    },
    
    // Disable analytics tracking
    disableAnalytics: function() {
        if (typeof gtag !== 'undefined') {
            gtag('consent', 'update', {
                analytics_storage: 'denied'
            });
        }
    },
    
    // Show consent banner (basic implementation)
    showConsentBanner: function() {
        if (!this.hasConsent() && !localStorage.getItem('consent_banner_shown')) {
            const banner = document.createElement('div');
            banner.className = 'consent-banner';
            banner.innerHTML = `
                <div class="consent-content">
                    <p>We use analytics to improve your experience. Do you consent to analytics tracking?</p>
                    <button onclick="PrivacyManager.setConsent(true); this.parentElement.parentElement.remove();">Accept</button>
                    <button onclick="PrivacyManager.setConsent(false); this.parentElement.parentElement.remove();">Decline</button>
                </div>
            `;
            
            document.body.appendChild(banner);
            localStorage.setItem('consent_banner_shown', 'true');
        }
    }
};

// Initialize Analytics on DOM Content Loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check for consent before initializing
    if (PrivacyManager.hasConsent()) {
        initGoogleAnalytics();
        setupAutomaticTracking();
        setupCalendlyTracking();
    } else {
        // Show consent banner
        PrivacyManager.showConsentBanner();
    }
});

// Utility function for throttling (reused from main.js)
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Export for global access
window.Analytics = Analytics;
window.PrivacyManager = PrivacyManager;

// Development mode detection
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('Analytics initialized in development mode');
    // Disable actual tracking in development
    window.gtag = function() {
        console.log('GA Event (dev mode):', arguments);
    };
}