<?php
/**
 * Plugin Name: Conclave ticket login
 * Description: Opens the dashboard for the site's administrator from a one-use ticket made over SSH. Holds no key.
 * Version: 1.0.0
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 *
 * How it works. `scripts/open-dashboard.py` makes a random token of 64 lower-case hex characters and stores only its
 * SHA-256 hash on the site, through WP-CLI over the project's pinned SSH connection, as one option: the hash, the
 * time it expires (60 seconds on) and the WordPress user it is for. It then opens `/?conclave_ticket=<token>`.
 * This plugin, on `init` at priority 1, takes that option off the site before it judges anything, so a ticket works
 * once and a wrong token uses it up. It reads the ticket's row and deletes it by that exact value, so of two requests
 * that read the same ticket only the one whose delete removed it goes on, and neither can use up a newer ticket. It
 * logs the user in only when the token has the right form, its hash matches, the ticket has not expired and the user
 * exists and holds `manage_options`. Anything else is a 403 with one fixed sentence.
 *
 * It holds no key and no secret: nothing on the site, in the repository or in a vault can make a login. A ticket
 * exists only while someone with SSH access to the site has just made one.
 *
 * @package Conclave
 */

defined( 'ABSPATH' ) || exit;

// One copy only: a site that already loads this file (a second copy under another name) declares nothing twice and
// registers no second handler.
if ( ! defined( 'CONCLAVE_TICKET_LOADED' ) ) {
	define( 'CONCLAVE_TICKET_LOADED', true );

	if ( ! defined( 'CONCLAVE_TICKET_OPTION' ) ) {
		define( 'CONCLAVE_TICKET_OPTION', 'conclave_login_ticket' );
	}
	if ( ! defined( 'CONCLAVE_TICKET_QUERY' ) ) {
		define( 'CONCLAVE_TICKET_QUERY', 'conclave_ticket' );
	}

	/**
	 * Ends the request with a 403 and one fixed sentence, whatever was wrong.
	 */
	function conclave_ticket_login_refuse() {
		wp_die(
			esc_html__( 'This login link is not valid. Make a new one with scripts/open-dashboard.py.', 'conclave-ticket-login' ),
			esc_html__( 'Login link not valid', 'conclave-ticket-login' ),
			array( 'response' => 403 )
		);
	}

	/**
	 * Redeems a ticket when the request carries one: consumed first, then judged, then the login.
	 */
	function conclave_ticket_login_redeem() {
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended -- the one-use ticket is the proof; a nonce needs a session this request does not have yet.
		if ( ! isset( $_GET[ CONCLAVE_TICKET_QUERY ] ) ) {
			return;
		}
		nocache_headers();
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended -- the one-use ticket is the proof; the value is held to 64 hex characters below before any use.
		$token = wp_unslash( $_GET[ CONCLAVE_TICKET_QUERY ] );
		$token = is_string( $token ) ? $token : '';

		// Consumed before it is judged, and bound to the very ticket read. The Options API deletes by name only, so a
		// request that read ticket A could delete a newer ticket B stored in between and still log in with A. The row
		// is therefore read straight from the table (no cache can hand back a ticket already used) and removed by its
		// exact value: only the request whose DELETE removed the ticket it read goes on.
		// WORKAROUND: the Options API (the owning layer) has no compare-and-delete, so the ticket's row is read and
		// deleted through $wpdb, the narrowest way WordPress offers; the cache entry is dropped after it.
		global $wpdb;
		$raw = $wpdb->get_var( $wpdb->prepare( "SELECT option_value FROM {$wpdb->options} WHERE option_name = %s", CONCLAVE_TICKET_OPTION ) );
		if ( ! is_string( $raw ) ) {
			conclave_ticket_login_refuse();
		}
		$removed = $wpdb->query( $wpdb->prepare( "DELETE FROM {$wpdb->options} WHERE option_name = %s AND option_value = %s", CONCLAVE_TICKET_OPTION, $raw ) );
		wp_cache_delete( CONCLAVE_TICKET_OPTION, 'options' );
		if ( 1 !== $removed ) {
			conclave_ticket_login_refuse();
		}
		$ticket = maybe_unserialize( $raw );
		if ( ! is_string( $token ) || 1 !== preg_match( '/^[0-9a-f]{64}$/', $token ) ) {
			conclave_ticket_login_refuse();
		}
		if ( ! is_array( $ticket ) || ! isset( $ticket['hash'], $ticket['expires'], $ticket['user'] ) ) {
			conclave_ticket_login_refuse();
		}
		if ( ! is_string( $ticket['hash'] ) || ! is_int( $ticket['expires'] ) || ! is_int( $ticket['user'] ) || $ticket['user'] < 1 ) {
			conclave_ticket_login_refuse();
		}
		if ( ! hash_equals( $ticket['hash'], hash( 'sha256', $token ) ) ) {
			conclave_ticket_login_refuse();
		}
		if ( time() > $ticket['expires'] ) {
			conclave_ticket_login_refuse();
		}
		$user = get_userdata( $ticket['user'] );
		if ( ! $user || ! user_can( $user, 'manage_options' ) ) {
			conclave_ticket_login_refuse();
		}

		wp_set_current_user( $user->ID );
		wp_set_auth_cookie( $user->ID, false );
		do_action( 'wp_login', $user->user_login, $user ); // WordPress's own login action, so an activity log records this login.
		wp_safe_redirect( admin_url() );
		exit;
	}

	add_action( 'init', 'conclave_ticket_login_redeem', 1 );
}
